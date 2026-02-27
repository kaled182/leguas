import re
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from django.core.exceptions import ObjectDoesNotExist
from .models import LearningPattern, ProcessingHistory

class IntelligentDataDetector:
    """IA avançada para detectar padrões em dados e aprender incrementalmente com sistema de ranking"""
    
    def __init__(self):
        self.patterns = self._load_patterns()
        # Inicializa o sistema de ranking
        self.ranking_data_path = os.path.join(os.path.dirname(__file__), 'ranking_data.json')
        self.ranking_data = self._load_ranking_data()
        
    def _load_ranking_data(self):
        """Carrega dados de ranking do arquivo JSON"""
        if os.path.exists(self.ranking_data_path):
            try:
                with open(self.ranking_data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erro ao carregar dados de ranking: {e}")
                return {"patterns": {}, "examples": {}, "corrections": [], "stats": {"accuracy": 0, "processed": 0}}
        else:
            return {"patterns": {}, "examples": {}, "corrections": [], "stats": {"accuracy": 0, "processed": 0}}
    
    def _save_ranking_data(self):
        """Salva dados de ranking no arquivo JSON"""
        try:
            with open(self.ranking_data_path, 'w', encoding='utf-8') as f:
                json.dump(self.ranking_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao salvar dados de ranking: {e}")
        
    def _load_patterns(self) -> Dict[str, List[Dict]]:
        """Carrega padrões aprendidos do banco de dados e do ranking"""
        patterns = {
            'endereco': [],
            'codigo_id': [],  # Renomeado de 'id' para 'codigo_id' para consistência
            'hora': [],
            'data': [],
            'litros': [],  # Renomeado de 'volume' para 'litros' para consistência
            'numero': [],
            'horario': [],
            'quantidade': []  # Adicionado campo quantidade
        }
        
        # Carregar patterns do ranking primeiro
        if hasattr(self, 'ranking_data') and self.ranking_data and 'patterns' in self.ranking_data:
            for field, field_patterns in self.ranking_data['patterns'].items():
                if field in patterns:
                    for pattern_info in field_patterns:
                        patterns[field].append({
                            'pattern': pattern_info['pattern'],
                            'confidence': pattern_info['score'] / 10,  # Normaliza de 0-10 para 0-1
                            'usage_count': pattern_info['usage_count'] if 'usage_count' in pattern_info else 1
                        })
        
        # Depois carregar patterns do banco de dados
        try:
            for pattern in LearningPattern.objects.all():
                if pattern.pattern_type in patterns:
                    patterns[pattern.pattern_type].append({
                        'pattern': pattern.pattern_value,
                        'confidence': pattern.confidence,
                        'usage_count': pattern.usage_count
                    })
        except Exception as e:
            print(f"Erro ao carregar padrões do banco de dados: {e}")
            # Continua com os padrões do ranking ou padrões padrão
            
            # Padrões iniciais com sistema de ranking (0-10 onde 10 é maior confiança)
        if not patterns['endereco']:
            patterns['endereco'] = [
                {'pattern': r'^(rua|r\.|av|av\.|avenida|travessa|largo|praça|estrada|via|quinta|beco)', 'confidence': 0.9, 'usage_count': 1},
                {'pattern': r'.*\d{4}-\d{3}.*', 'confidence': 0.95, 'usage_count': 1},  # código postal português
                {'pattern': r'.*,\s*\d{4}-\d{3},.*', 'confidence': 0.98, 'usage_count': 1},  # formato completo com código postal
                {'pattern': r'^.+\d+[a-zA-Z]?,.*\d{4}-\d{3}', 'confidence': 0.97, 'usage_count': 1},  # rua + número + código postal
                {'pattern': r'.*ponte\s+de\s+lima.*', 'confidence': 0.8, 'usage_count': 1},  # localidade comum
                {'pattern': r'.*riba\s+de\s+âncora.*', 'confidence': 0.8, 'usage_count': 1},  # outra localidade
                {'pattern': r'^(?!#)(?!Local ID:).*', 'confidence': 0.6, 'usage_count': 1}  # qualquer coisa que não seja ID
            ]
            
        if not patterns['codigo_id']:
            patterns['codigo_id'] = [
                {'pattern': r'^#[A-Za-z0-9_]+', 'confidence': 0.95, 'usage_count': 1},
                {'pattern': r'^#[A-Za-z0-9_]+_\d+', 'confidence': 0.95, 'usage_count': 1},
                {'pattern': r'^#[EUJUW][a-zA-Z0-9]+_\d+', 'confidence': 0.98, 'usage_count': 1},  # Formato dos IDs na captura
                {'pattern': r'^#\d+', 'confidence': 0.97, 'usage_count': 1},  # Formato #números como na captura
                {'pattern': r'^[A-Z]\d+[A-Za-z]*', 'confidence': 0.7, 'usage_count': 1},
                {'pattern': r'^\d{9,15}$', 'confidence': 0.6, 'usage_count': 1}
            ]
            
        if not patterns['hora']:
            patterns['hora'] = [
                {'pattern': r'^\d{1,2}:\d{2}$', 'confidence': 0.9, 'usage_count': 1}
            ]
            
        if not patterns['data']:
            patterns['data'] = [
                {'pattern': r'^(today|hoje|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})$', 'confidence': 0.9, 'usage_count': 1}
            ]
            
        if not patterns['litros']:
            patterns['litros'] = [
                {'pattern': r'^\d+(\.\d+)?\s*L$', 'confidence': 0.9, 'usage_count': 1},
                {'pattern': r'^\d+(\.\d+)?$', 'confidence': 0.7, 'usage_count': 1}
            ]
            
        if not patterns['horario']:
            patterns['horario'] = [
                {'pattern': r'^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$', 'confidence': 0.9, 'usage_count': 1}
            ]
            
        if not patterns['numero']:
            patterns['numero'] = [
                {'pattern': r'^\d+$', 'confidence': 0.8, 'usage_count': 1}
            ]
            
        if not patterns['quantidade']:
            patterns['quantidade'] = [
                {'pattern': r'^\d+$', 'confidence': 0.7, 'usage_count': 1}
            ]
            
        return patterns
        
    def detect_field_type(self, text: str) -> Tuple[str, float]:
        """Detecta o tipo de campo baseado no texto usando sistema de ranking"""
        text = text.strip()
        if not text:
            return 'unknown', 0.0
            
        best_match = ('unknown', 0.0)
        matches = {}
        
        # Coleta todos os matches com pontuações
        for field_type, pattern_list in self.patterns.items():
            field_score = 0
            for pattern_info in pattern_list:
                pattern = pattern_info['pattern']
                confidence = pattern_info['confidence']
                
                if re.search(pattern, text, re.IGNORECASE):
                    # Usa usage_count como fator de boost para padrões frequentemente usados
                    boost = min(1 + (pattern_info['usage_count'] * 0.1), 2.0)  # Limita o boost a 2x
                    current_score = confidence * boost
                    field_score = max(field_score, current_score)
            
            if field_score > 0:
                matches[field_type] = field_score
        
        # Regras especiais para campos específicos
        # Endereço: check para CEP/códigos postais e palavras-chave
        if text.startswith(('rua', 'r.', 'av', 'av.', 'avenida', 'travessa', 'largo', 'praça', 'estrada', 'via', 'quinta', 'beco')):
            matches['endereco'] = max(matches.get('endereco', 0), 0.95)
        elif re.search(r'\d{4,5}[\-\s]*\d{3}', text):  # CEP/código postal
            matches['endereco'] = max(matches.get('endereco', 0), 0.85)
        elif 'ponte de lima' in text.lower():  # Localidade comum
            matches['endereco'] = max(matches.get('endereco', 0), 0.7)
        
        # Código ID
        if text.startswith('#'):
            matches['codigo_id'] = max(matches.get('codigo_id', 0), 0.95)
        
        # Litros
        if text.endswith('L') and re.search(r'\d', text):
            matches['litros'] = max(matches.get('litros', 0), 0.95)
        
        # Hora
        if re.match(r'^\d{1,2}:\d{2}$', text):
            matches['hora'] = max(matches.get('hora', 0), 0.95)
        
        # Data
        if text.lower() == 'today':
            matches['data'] = max(matches.get('data', 0), 0.98)
            
        # Horário
        if re.match(r'^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$', text):
            matches['horario'] = max(matches.get('horario', 0), 0.95)
        
        # Encontra o match com maior pontuação
        for field_type, score in matches.items():
            if score > best_match[1]:
                best_match = (field_type, score)
        
        return best_match
    
    def parse_intelligent_blocks(self, raw_text: str) -> List[Dict]:
        """
        Parse inteligente dos blocos de dados seguindo as regras específicas:
        
        Cada bloco contém:
        Linha 1: Endereço completo (rua, número, código postal, localidade)
        Linha 2: Código ID (formato #XxxXxxXx_1)
        Linha 3: Endereço repetido (ignorar)
        Linha 4: Ordem/Número de sequência
        Linha 5: (vazia)
        Linha 6: Horário de início (HH:MM)
        Linha 7: (vazia)  
        Linha 8: Data ("Today")
        Linha 9: (vazia)
        Linha 10: Horário de funcionamento (HH:MM - HH:MM)
        Linha 11: Quantidade com unidade (ex: 1.6497 L)
        Linha 12: Ordem final
        """
        if not raw_text or not raw_text.strip():
            return []
            
        # Pré-processamento: remove linhas de rodapé como "1-25 of 73", "26-50 of 73"
        linhas = []
        for linha in raw_text.splitlines():
            linha_limpa = linha.strip()
            # Remove linhas de paginação
            if not re.match(r'^\d+-\d+\s+of\s+\d+$', linha_limpa):
                linhas.append(linha_limpa)
        
        # Identificar blocos - cada bloco começa com um endereço seguido de um código ID
        blocos = []
        i = 0
        
        while i < len(linhas):
            linha_atual = linhas[i].strip()
            
            # Pula linhas vazias
            if not linha_atual:
                i += 1
                continue
            
            # Verifica se a próxima linha não vazia é um ID (começa com #)
            proxima_linha_id = None
            j = i + 1
            while j < len(linhas) and not linhas[j].strip():
                j += 1
            
            if j < len(linhas) and linhas[j].strip().startswith('#'):
                proxima_linha_id = j
            
            # Se encontramos um endereço seguido de ID, inicia um novo bloco
            if proxima_linha_id is not None and not linha_atual.startswith('#'):
                # Coleta todo o bloco até o próximo endereço + ID
                bloco_atual = []
                
                # Adiciona a linha atual (endereço)
                bloco_atual.append(linha_atual)
                i += 1
                
                # Adiciona todas as linhas até encontrar o próximo padrão endereço + ID
                while i < len(linhas):
                    linha = linhas[i].strip()
                    bloco_atual.append(linha)
                    
                    # Verifica se a próxima linha não vazia seria o início de um novo bloco
                    # (endereço seguido de ID)
                    if i + 1 < len(linhas):
                        proxima_linha = linhas[i + 1].strip()
                        # Se a próxima linha não vazia é um endereço...
                        if (proxima_linha and not proxima_linha.startswith('#')):
                            # ...verifica se depois dela vem um ID
                            k = i + 2
                            while k < len(linhas) and not linhas[k].strip():
                                k += 1
                            if k < len(linhas) and linhas[k].strip().startswith('#'):
                                # Próximo bloco encontrado, para aqui
                                break
                    
                    i += 1
                
                if bloco_atual and len(bloco_atual) > 1:
                    blocos.append(bloco_atual)
            else:
                i += 1
        
        # Registra estatísticas no sistema de ranking
        self.ranking_data['stats']['processed'] += 1
        
        # Processar cada bloco seguindo as regras específicas
        dados_estruturados = []
        for i, bloco in enumerate(blocos):
            # Debug: print do bloco sendo processado
            print(f"Processando bloco {i + 1}: {bloco}")
            
            dados = self._process_structured_block(bloco, i + 1)
            
            if dados:
                print(f"Bloco {i + 1} processado com sucesso: {dados}")
                dados_estruturados.append(dados)
            else:
                print(f"Falha ao processar bloco {i + 1}")
        
        print(f"Total de blocos processados: {len(dados_estruturados)}")
        return dados_estruturados
    
    def _process_structured_block(self, bloco: List[str], block_id: int) -> Optional[Dict]:
        """
        Processa um bloco de forma inteligente e flexível, identificando automaticamente
        os diferentes tipos de dados baseado em padrões, independente da posição.
        """
        print(f"_process_structured_block: processando bloco com {len(bloco)} linhas: {bloco}")
        
        # Precisa ter pelo menos 2 linhas para ser válido (endereço + ID mínimo)
        if len(bloco) < 2:
            print(f"_process_structured_block: bloco muito pequeno ({len(bloco)} linhas)")
            return None
        
        resultado = {
            'id': block_id,
            'endereco': '',
            'codigo_id': '',
            'numero': '',
            'hora': '',
            'data': '',
            'horario': '',
            'litros': '',
            'quantidade': '',
            'confidence_scores': {}
        }
        
        # Flags para controlar o que já foi encontrado
        flags_encontrados = {
            'codigo': False,
            'endereco': False,
            'numero': False,
            'hora': False,
            'data': False,
            'horario': False,
            'litros': False,
            'quantidade': False
        }
        
        # Processa cada linha identificando o tipo de dados
        for i, linha in enumerate(bloco):
            linha_limpa = linha.strip()
            if not linha_limpa:
                continue
                
            print(f"Analisando linha {i}: '{linha_limpa}'")
            
            # 1. Código ID (prioridade máxima - deve começar com #)
            if linha_limpa.startswith('#') and not flags_encontrados['codigo']:
                resultado['codigo_id'] = linha_limpa
                resultado['confidence_scores']['codigo_id'] = 0.99
                flags_encontrados['codigo'] = True
                print(f"✓ Código ID: {linha_limpa}")
                continue
            
            # 2. Endereço (primeira linha longa que não é código nem número)
            if not flags_encontrados['endereco'] and not linha_limpa.startswith('#') and not linha_limpa.isdigit():
                # Critérios para identificar endereço:
                # - Contém palavras típicas de endereço
                # - Contém código postal (formato XXXX-XXX)
                # - É uma linha relativamente longa (mais de 10 caracteres)
                # - Contém pelo menos uma vírgula (separando partes do endereço)
                
                criterios_endereco = [
                    any(palavra in linha_limpa.lower() for palavra in ['rua', 'av', 'avenida', 'largo', 'praça', 'estrada', 'via', 'quinta', 'beco', 'travessa', 'alameda']),
                    re.search(r'\d{4,5}[\-\s]*\d{3}', linha_limpa),  # Código postal
                    len(linha_limpa) > 10,
                    ',' in linha_limpa
                ]
                
                if any(criterios_endereco):
                    endereco_normalizado = self._normalize_address(linha_limpa)
                    resultado['endereco'] = endereco_normalizado
                    resultado['confidence_scores']['endereco'] = 0.95
                    flags_encontrados['endereco'] = True
                    print(f"✓ Endereço: {endereco_normalizado}")
                    continue
            
            # 3. Hora (formato HH:MM, mas não intervalo)
            if not flags_encontrados['hora'] and re.match(r'^\d{1,2}:\d{2}$', linha_limpa):
                resultado['hora'] = linha_limpa
                resultado['confidence_scores']['hora'] = 0.98
                flags_encontrados['hora'] = True
                print(f"✓ Hora: {linha_limpa}")
                continue
            
            # 4. Horário de funcionamento (formato HH:MM - HH:MM)
            if not flags_encontrados['horario'] and re.match(r'^\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}', linha_limpa):
                resultado['horario'] = linha_limpa
                resultado['confidence_scores']['horario'] = 0.98
                flags_encontrados['horario'] = True
                print(f"✓ Horário funcionamento: {linha_limpa}")
                continue
            
            # 5. Data ("Today" ou formatos de data)
            if not flags_encontrados['data']:
                if linha_limpa.lower() == 'today' or re.match(r'^\d{1,2}[/-]\d{1,2}', linha_limpa):
                    resultado['data'] = linha_limpa
                    resultado['confidence_scores']['data'] = 0.98
                    flags_encontrados['data'] = True
                    print(f"✓ Data: {linha_limpa}")
                    continue
            
            # 6. Litros (número com L ou decimal)
            if not flags_encontrados['litros']:
                if re.search(r'\d+(\.\d+)?\s*L', linha_limpa, re.IGNORECASE):
                    resultado['litros'] = linha_limpa
                    resultado['confidence_scores']['litros'] = 0.98
                    flags_encontrados['litros'] = True
                    print(f"✓ Litros: {linha_limpa}")
                    continue
                # Números decimais também podem ser litros
                elif re.match(r'^\d+\.\d+$', linha_limpa):
                    resultado['litros'] = linha_limpa
                    resultado['confidence_scores']['litros'] = 0.85
                    flags_encontrados['litros'] = True
                    print(f"✓ Litros (decimal): {linha_limpa}")
                    continue
            
            # 7. Número de ordem/sequência (1-3 dígitos, mas não se já temos)
            if not flags_encontrados['numero'] and re.match(r'^\d{1,3}$', linha_limpa):
                resultado['numero'] = linha_limpa
                resultado['confidence_scores']['numero'] = 0.90
                flags_encontrados['numero'] = True
                print(f"✓ Número: {linha_limpa}")
                continue
            
            # 8. Quantidade (pequeno número inteiro, geralmente no final)
            if not flags_encontrados['quantidade'] and re.match(r'^\d{1,2}$', linha_limpa):
                # Se já temos número, este pode ser quantidade
                if flags_encontrados['numero']:
                    resultado['quantidade'] = linha_limpa
                    resultado['confidence_scores']['quantidade'] = 0.85
                    flags_encontrados['quantidade'] = True
                    print(f"✓ Quantidade: {linha_limpa}")
                    continue
        
        # Pós-processamento: endereço alternativo
        if not resultado['endereco'] and resultado['codigo_id']:
            # Se não encontrou endereço mas tem ID, usa a primeira linha como endereço
            for linha in bloco:
                linha_limpa = linha.strip()
                if linha_limpa and not linha_limpa.startswith('#') and len(linha_limpa) > 5:
                    resultado['endereco'] = self._normalize_address(linha_limpa)
                    resultado['confidence_scores']['endereco'] = 0.60
                    print(f"✓ Endereço alternativo: {resultado['endereco']}")
                    break
        
        # Valores padrão para campos não encontrados
        if not resultado['quantidade']:
            resultado['quantidade'] = '1'
            resultado['confidence_scores']['quantidade'] = 0.50
        
        # Validação final: deve ter pelo menos código ID
        if not resultado['codigo_id']:
            print(f"✗ _process_structured_block: falha - nenhum código ID encontrado")
            return None
        
        print(f"✓ _process_structured_block: sucesso - dados extraídos: {resultado}")
        return resultado
        
    def _normalize_address(self, endereco: str) -> str:
        """
        Normaliza um endereço seguindo as regras:
        - Capitaliza adequadamente palavras
        - Mantém códigos postais e números como estão
        - Remove repetições desnecessárias
        - Trata códigos postais no início do endereço adequadamente
        """
        if not endereco:
            return ""
        
        # Remove espaços extras e quebras de linha
        endereco = ' '.join(endereco.split())
        
        # Verifica se começa com código postal (formato XXXX-XXX)
        codigo_postal = None
        localidade = None
        rua_numero = None
        
        # Extrai código postal se estiver no início
        if re.match(r'^\d{4}-\d{3}', endereco):
            # Exemplo: 4980-017rua da Granja, 4980-017, Viana do Castelo
            partes = re.split(r'(\d{4}-\d{3})', endereco, maxsplit=1)
            if len(partes) > 2:
                codigo_postal = partes[1]
                resto = partes[2]
            
                # Procura por outro código postal e cidade
                match = re.search(r',\s*\d{4}-\d{3},\s*([^,]+)$', resto)
                if match:
                    localidade = match.group(1).strip()
                    rua_numero = resto[:match.start()].strip()
                else:
                    rua_numero = resto.strip()
        else:
            # Divide o endereço em partes por vírgula
            partes = [parte.strip() for parte in endereco.split(',')]
            
            for parte in partes:
                if re.match(r'^\d{4}-\d{3}$', parte):
                    codigo_postal = parte
                elif codigo_postal and not localidade:  # A parte após o código postal é geralmente a localidade
                    localidade = parte
                elif not rua_numero:
                    rua_numero = parte
        
        # Se encontrou rua_numero, capitaliza adequadamente
        if rua_numero:
            rua_numero = self._capitalize_address_part(rua_numero)
        
        # Se encontrou localidade, capitaliza adequadamente
        if localidade:
            localidade = self._capitalize_address_part(localidade)
        
        # Monta o endereço normalizado
        partes_finais = []
        
        if rua_numero:
            partes_finais.append(rua_numero)
        
        if codigo_postal:
            partes_finais.append(codigo_postal)
            
        if localidade:
            partes_finais.append(localidade)
            
        # Junta as partes com espaço
        return ' '.join(partes_finais)
    
    def _capitalize_address_part(self, parte: str) -> str:
        """
        Capitaliza uma parte do endereço adequadamente
        """
        # Palavras que devem ficar em minúscula (preposições, artigos)
        palavras_minusculas = {'de', 'da', 'do', 'das', 'dos', 'e', 'a', 'o', 'em', 'na', 'no'}
        
        palavras = parte.lower().split()
        resultado = []
        
        for i, palavra in enumerate(palavras):
            # Primeira palavra sempre capitalizada
            if i == 0:
                resultado.append(palavra.capitalize())
            # Palavras pequenas ficam minúsculas, exceto se for a primeira
            elif palavra in palavras_minusculas:
                resultado.append(palavra)
            # Outras palavras são capitalizadas
            else:
                resultado.append(palavra.capitalize())
        
        return ' '.join(resultado)
    
    def _process_block_intelligently(self, bloco: List[str], block_id: int) -> Optional[Dict]:
        """Processa um bloco individual com detecção inteligente quando o formato específico falha"""
        if len(bloco) < 2:
            return None
            
        resultado = {
            'id': block_id,
            'endereco': '',
            'codigo_id': '',
            'numero': '',
            'hora': '',
            'data': '',
            'horario': '',
            'litros': '',
            'quantidade': '',
            'confidence_scores': {}
        }
        
        # Identificar estrutura baseado no formato esperado
        # Primeira linha geralmente é endereço
        # Segunda linha geralmente é código ID
        # Depois vem número, hora, data, horário, litros, quantidade
        
        # Estrutura esperada:
        # [0] = endereço
        # [1] = código ID (começa com #)
        # [2] = número
        # [3] = hora (formato HH:MM)
        # [4] = data (geralmente "Today")
        # [5] = horário (formato HH:MM - HH:MM)
        # [6] = litros (pode conter "L")
        # [7] = quantidade
        
        # Primeiro, encontrar o índice do ID (linha que começa com #)
        id_index = -1
        for idx, linha in enumerate(bloco):
            if linha.startswith('#'):
                id_index = idx
                break
        
        if id_index == -1:  # Se não encontrar ID, tenta processar usando detecção de campo
            # Processamento alternativo para blocos sem ID claro
            for idx, linha in enumerate(bloco):
                field_type, confidence = self.detect_field_type(linha)
                
                # Só aceita se a confiança for razoável
                if confidence > 0.5:
                    if field_type == 'endereco' and not resultado['endereco']:
                        resultado['endereco'] = linha
                        resultado['confidence_scores']['endereco'] = confidence
                    elif field_type == 'codigo_id' and not resultado['codigo_id']:
                        resultado['codigo_id'] = linha
                        resultado['confidence_scores']['codigo_id'] = confidence
                    elif field_type == 'hora' and not resultado['hora']:
                        resultado['hora'] = linha
                        resultado['confidence_scores']['hora'] = confidence
                    elif field_type == 'data' and not resultado['data']:
                        resultado['data'] = linha
                        resultado['confidence_scores']['data'] = confidence
                    elif field_type == 'horario' and not resultado['horario']:
                        resultado['horario'] = linha
                        resultado['confidence_scores']['horario'] = confidence
                    elif field_type == 'litros' and not resultado['litros']:
                        resultado['litros'] = linha
                        resultado['confidence_scores']['litros'] = confidence
                    elif linha.isdigit() and not resultado['numero']:
                        resultado['numero'] = linha
                    elif linha.isdigit() and not resultado['quantidade']:
                        resultado['quantidade'] = linha
        else:
            # Processamento baseado no índice do ID encontrado
            # Primeiro, identificamos o endereço (geralmente antes do ID)
            if id_index > 0:
                resultado['endereco'] = bloco[id_index-1]
                resultado['confidence_scores']['endereco'] = 0.9
            else:
                # Se não encontramos um endereço, usamos o próprio ID como informação de endereço
                # Isso ajuda a IA a aprender que IDs também podem conter informações relacionadas ao endereço
                resultado['endereco'] = f"Local ID: {bloco[id_index]}"
                resultado['confidence_scores']['endereco'] = 0.6
            
            # Agora o ID
            resultado['codigo_id'] = bloco[id_index]
            resultado['confidence_scores']['codigo_id'] = 0.95
            
            # Itens após o ID
            if id_index + 1 < len(bloco) and bloco[id_index+1].strip():
                # Se o próximo item após o ID é um endereço novamente, pulamos ele
                if bloco[id_index+1].lower().startswith(('rua', 'av', 'avenida', 'travessa', 'r.', 'via')):
                    start_idx = id_index + 2
                else:
                    start_idx = id_index + 1
                
                # Agora processamos os itens na sequência esperada
                for offset, field in enumerate(bloco[start_idx:]):
                    if not field.strip():
                        continue
                    
                    # Determinar campo baseado na posição relativa e no conteúdo
                    if offset == 0:  # Número
                        resultado['numero'] = field
                    elif offset == 1 and re.match(r'^\d{1,2}:\d{2}$', field):  # Hora
                        resultado['hora'] = field
                        resultado['confidence_scores']['hora'] = 0.9
                    elif offset == 2 and field.lower() in ['today', 'hoje']:  # Data
                        resultado['data'] = field
                        resultado['confidence_scores']['data'] = 0.9
                    elif offset == 3 and re.match(r'^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$', field):  # Horário
                        resultado['horario'] = field
                        resultado['confidence_scores']['horario'] = 0.9
                    elif offset == 4 and (field.endswith('L') or re.match(r'^\d+(\.\d+)?', field)):  # Litros
                        resultado['litros'] = field
                        resultado['confidence_scores']['litros'] = 0.85
                    elif offset == 5:  # Quantidade
                        resultado['quantidade'] = field
        
        return resultado
    
    def learn_from_corrections(self, original_data: str, corrected_data: List[Dict]):
        """Aprende com as correções do usuário usando sistema de ranking"""
        try:
            # Salvar histórico no banco de dados
            history = ProcessingHistory.objects.create(
                original_data=original_data,
                processed_data=json.dumps(corrected_data, ensure_ascii=False),
                user_corrections=json.dumps(corrected_data, ensure_ascii=False)
            )
            
            # Inicializa o registro de correções no ranking
            correction_record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "corrections": [],
                "fields_changed": {}
            }
            
            # Para cada item corrigido
            for item in corrected_data:
                # Verifica campos com valores
                for field, value in item.items():
                    if field in ['endereco', 'codigo_id', 'hora', 'data', 'horario', 'litros', 'quantidade'] and value:
                        # Atualiza o padrão no DB
                        self._update_pattern(field, value)
                        
                        # Adiciona ao sistema de ranking
                        pattern_tuple = self._create_pattern_for_ranking(field, value)
                        
                        if pattern_tuple:
                            pattern, score = pattern_tuple
                            
                            # Registra a correção
                            if field not in correction_record["fields_changed"]:
                                correction_record["fields_changed"][field] = 0
                            correction_record["fields_changed"][field] += 1
                            
                            # Adiciona ou atualiza o padrão no ranking
                            if field not in self.ranking_data["patterns"]:
                                self.ranking_data["patterns"][field] = []
                                
                            # Verifica se padrão já existe
                            found = False
                            for p in self.ranking_data["patterns"][field]:
                                if p["pattern"] == pattern:
                                    p["score"] = min(10, p["score"] + 0.5)  # Aumenta score (max 10)
                                    p["usage_count"] = p.get("usage_count", 0) + 1
                                    p["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    found = True
                                    break
                                    
                            if not found:
                                self.ranking_data["patterns"][field].append({
                                    "pattern": pattern,
                                    "score": score,
                                    "usage_count": 1,
                                    "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "last_used": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "example": value
                                })
                            
                            # Adiciona exemplo para aprendizado
                            if field not in self.ranking_data["examples"]:
                                self.ranking_data["examples"][field] = []
                            
                            # Adiciona o exemplo apenas se não existir um igual
                            if value not in self.ranking_data["examples"][field]:
                                self.ranking_data["examples"][field].append(value)
            
            # Adiciona registro de correção
            if any(correction_record["fields_changed"].values()):
                self.ranking_data["corrections"].append(correction_record)
            
            # Atualiza estatísticas
            accuracy = self.calculate_accuracy()
            self.ranking_data["stats"]["accuracy"] = accuracy
            
            # Salva os dados de ranking
            self._save_ranking_data()
                        
        except Exception as e:
            print(f"Erro ao aprender com correções: {e}")
    
    def _create_pattern_for_ranking(self, field_type, value):
        """Cria um padrão otimizado para o sistema de ranking"""
        if not value:
            return None
            
        value = value.strip()
        
        # Diferentes padrões baseados no tipo de campo
        if field_type == 'endereco':
            # Verifica se é um endereço com código postal português
            if re.search(r'\d{4}-\d{3}', value):
                return (r'.*\d{4}-\d{3}.*', 9.5)  # Padrão de código postal português
                
            # Verifica se começa com tipo de via
            words = value.lower().split()
            if not words:
                return None
                
            if words[0] in ['rua', 'r.', 'av.', 'av', 'avenida', 'travessa', 'largo', 'praça', 'estrada', 'via', 'quinta', 'beco']:
                return (f"^{re.escape(words[0])}\\s", 9)  # Padrão para início do endereço
                
            # Verifica se contém localidades portuguesas conhecidas
            value_lower = value.lower()
            localidades = ['ponte de lima', 'riba de âncora', 'viana do castelo', 'braga', 'porto']
            for localidade in localidades:
                if localidade in value_lower:
                    return (f".*{re.escape(localidade)}", 8)
                    
            # Padrão genérico para endereços que não começam com Local ID:
            if not value.startswith(('Local ID:', '#')):
                return (r'^(?!#)(?!Local ID:).*', 7)
                
            # Padrão genérico baseado na primeira palavra
            return (f"^{re.escape(words[0])}\\s", 6)
            
        elif field_type == 'codigo_id':
            if value.startswith('#'):
                # Padrões específicos para os IDs como mostrados na captura
                if re.match(r'^#[EUJUW][a-zA-Z0-9]+_\d+', value):
                    return (r'^#[EUJUW][a-zA-Z0-9]+_\d+', 9.5)  # Formato #UxXxxXx_1
                elif re.match(r'^#\d+', value):
                    return (r'^#\d+', 9.5)  # Formato #números
                elif '_' in value:
                    return (r'^#[\w\d]+_\d+', 9)  # Padrão para IDs com underscore
                return (r'^#[\w\d]+', 8)  # Padrão para IDs começando com #
            elif value.isdigit() and len(value) > 8:
                return (f"^\\d{{{len(value)}}}$", 7)  # Padrão para IDs numéricos longos
                
        elif field_type == 'hora':
            if re.match(r'^\d{1,2}:\d{2}$', value):
                return (r'^\d{1,2}:\d{2}$', 9)
                
        elif field_type == 'data':
            if value.lower() == 'today':
                return (r'^today$', 10)
            elif re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}$', value):
                return (r'^\d{1,2}/\d{1,2}/\d{2,4}$', 9)
                
        elif field_type == 'horario':
            if re.match(r'^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$', value):
                return (r'^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$', 9)
                
        elif field_type == 'litros':
            if 'L' in value and re.match(r'^\d+(\.\d+)?\s*L$', value):
                return (r'^\d+(\.\d+)?\s*L$', 9)
            elif re.match(r'^\d+(\.\d+)?$', value):
                return (r'^\d+(\.\d+)?$', 7)
                
        elif field_type == 'quantidade':
            if value.isdigit():
                return (r'^\d+$', 8)
                
        # Fallback: criar um padrão específico para este valor
        return (f"^{re.escape(value)}$", 6)
    
    def _update_pattern(self, field_type: str, value: str):
        """Atualiza ou cria novos padrões baseado nos dados corrigidos no DB"""
        try:
            # Gerar padrão simples baseado no valor
            if field_type == 'endereco':
                # Extrair padrões de endereço
                if re.match(r'^(rua|r\.|av|av\.|avenida)', value, re.IGNORECASE):
                    pattern = r'^(rua|r\.|av|av\.|avenida)'
                elif re.match(r'^(largo|praça|estrada|via)', value, re.IGNORECASE):
                    pattern = r'^(largo|praça|estrada|via)'
                elif re.search(r'\d{4,5}[\-\s]*\d{3}', value):  # CEP/código postal
                    pattern = r'.*\d{4,5}[\-\s]*\d{3}'
                else:
                    return  # Não criar padrão se não identificar
                    
            elif field_type == 'codigo_id':
                if value.startswith('#'):
                    if '_' in value:
                        pattern = r'^#[\w\d]+_\d+'
                    else:
                        pattern = r'^#[\w\d]+'
                else:
                    pattern = f'^{re.escape(value[:3])}'  # primeiros 3 chars
                    
            elif field_type == 'hora':
                pattern = r'^\d{1,2}:\d{2}$'
                
            elif field_type == 'data':
                if value.lower() == 'today':
                    pattern = r'^today$'
                else:
                    pattern = r'^\d{1,2}[/-]\d{1,2}'
                    
            elif field_type == 'horario':
                pattern = r'^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$'
                
            elif field_type == 'litros':
                if 'L' in value:
                    pattern = r'^\d+(\.\d+)?\s*L$'
                else:
                    pattern = r'^\d+(\.\d+)?$'
                    
            elif field_type == 'quantidade':
                if value.isdigit():
                    pattern = r'^\d+$'
                else:
                    return
            else:
                return
            
            # Tentar atualizar padrão existente ou criar novo no banco de dados
            try:
                learning_pattern = LearningPattern.objects.get(
                    pattern_type=field_type,
                    pattern_value=pattern
                )
                learning_pattern.usage_count += 1
                learning_pattern.confidence = min(0.95, learning_pattern.confidence + 0.05)
                learning_pattern.save()
            except ObjectDoesNotExist:
                LearningPattern.objects.create(
                    pattern_type=field_type,
                    pattern_value=pattern,
                    confidence=0.7,
                    usage_count=1
                )
                
        except Exception as e:
            print(f"Erro ao atualizar padrão no DB: {e}")
    
    def calculate_accuracy(self):
        """Calcula a precisão atual do modelo de ranking"""
        if not hasattr(self, 'ranking_data') or not self.ranking_data:
            return 0
            
        patterns_count = 0
        weighted_score = 0
        
        for field, patterns in self.ranking_data.get("patterns", {}).items():
            for pattern in patterns:
                patterns_count += 1
                weighted_score += pattern["score"] * min(2, pattern.get("usage_count", 1) / 5 + 1)
        
        if patterns_count == 0:
            return 0
            
        # Normaliza para 0-100
        return min(100, weighted_score / (patterns_count * 10) * 100)
    
    def get_confidence_report(self, data: List[Dict]) -> Dict:
        """Gera relatório de confiança usando o sistema de ranking"""
        report = {
            'total_items': len(data),
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'fields_confidence': {},
            'ranking_stats': {
                'accuracy': self.calculate_accuracy(),
                'patterns_learned': sum(len(patterns) for patterns in self.ranking_data.get("patterns", {}).values()),
                'corrections_made': len(self.ranking_data.get("corrections", [])),
                'examples_collected': sum(len(examples) for examples in self.ranking_data.get("examples", {}).values())
            }
        }
        
        for item in data:
            confidence_scores = item.get('confidence_scores', {})
            avg_confidence = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0
            
            if avg_confidence > 0.8:
                report['high_confidence'] += 1
            elif avg_confidence > 0.5:
                report['medium_confidence'] += 1
            else:
                report['low_confidence'] += 1
                
            for field, score in confidence_scores.items():
                if field not in report['fields_confidence']:
                    report['fields_confidence'][field] = []
                report['fields_confidence'][field].append(score)
        
        # Calcular médias de confiança por campo
        field_averages = {}
        for field, scores in report['fields_confidence'].items():
            if scores:
                field_averages[field] = sum(scores) / len(scores)
            else:
                field_averages[field] = 0
                
        report['field_averages'] = field_averages
        
        return report
