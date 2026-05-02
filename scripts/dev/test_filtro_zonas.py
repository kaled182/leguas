"""
Script de Teste Rápido: Filtro por Zona no POC Delnext

Exemplos práticos de como usar o parâmetro zone_filter
"""

from playwright.sync_api import sync_playwright, Page
from pathlib import Path
import json


def test_zone_filter_examples():
    """Testa diferentes configurações de filtro"""
    
    from delnext_poc_playwright import DelnextPlaywrightPOC
    
    poc = DelnextPlaywrightPOC()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=True para produção
        page = browser.new_page()
        
        # Login
        print("🔐 Fazendo login...")
        if not poc.login(page):
            print("❌ Falha no login")
            browser.close()
            return
        
        print("\n" + "="*60)
        print("EXEMPLO 1: Filtrar apenas VianaCastelo")
        print("="*60)
        
        outbound_viana = poc.scrape_outbound(
            page, 
            test_date="Feb 27, 2026",
            zone_filter="VianaCastelo"
        )
        
        print(f"\n📊 Resultado: {len(outbound_viana)} entregas para VianaCastelo")
        if outbound_viana:
            print(f"   Exemplo: {outbound_viana[0]['product_id']} - {outbound_viana[0]['city']}")
        
        
        print("\n" + "="*60)
        print("EXEMPLO 2: Filtrar todas as zonas de Lisboa")
        print("="*60)
        
        outbound_lisboa = poc.scrape_outbound(
            page, 
            test_date="Feb 27, 2026",
            zone_filter="Lisboa"
        )
        
        print(f"\n📊 Resultado: {len(outbound_lisboa)} entregas para Lisboa (todas zonas)")
        if outbound_lisboa:
            # Mostrar zonas únicas
            zonas_lisboa = set([item['destination_zone'] for item in outbound_lisboa])
            print(f"   Zonas encontradas: {', '.join(zonas_lisboa)}")
        
        
        print("\n" + "="*60)
        print("EXEMPLO 3: SEM filtro (todas as zonas)")
        print("="*60)
        
        outbound_all = poc.scrape_outbound(
            page, 
            test_date="Feb 27, 2026",
            zone_filter=None  # Sem filtro
        )
        
        print(f"\n📊 Resultado: {len(outbound_all)} entregas TOTAIS")
        
        # Análise de zonas
        if outbound_all:
            zonas_count = {}
            for item in outbound_all:
                zona = item['destination_zone']
                zonas_count[zona] = zonas_count.get(zona, 0) + 1
            
            print("\n   📍 Distribuição por zona:")
            for zona, count in sorted(zonas_count.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(outbound_all)) * 100
                print(f"      • {zona}: {count} entregas ({percentage:.1f}%)")
        
        
        print("\n" + "="*60)
        print("EXEMPLO 4: Comparação de performance")
        print("="*60)
        
        import time
        
        # Teste 1: Com filtro
        start = time.time()
        filtered = poc.scrape_outbound(page, test_date="Feb 27, 2026", zone_filter="VianaCastelo")
        time_filtered = time.time() - start
        
        # Teste 2: Sem filtro
        start = time.time()
        all_data = poc.scrape_outbound(page, test_date="Feb 27, 2026", zone_filter=None)
        time_all = time.time() - start
        
        print(f"\n   ⏱️ Tempo com filtro: {time_filtered:.2f}s")
        print(f"   ⏱️ Tempo sem filtro: {time_all:.2f}s")
        print(f"   📊 Dados retornados: {len(filtered)} vs {len(all_data)}")
        
        # Tamanho JSON
        json_filtered = json.dumps(filtered, ensure_ascii=False)
        json_all = json.dumps(all_data, ensure_ascii=False)
        
        print(f"\n   💾 Tamanho JSON filtrado: {len(json_filtered)} bytes")
        print(f"   💾 Tamanho JSON completo: {len(json_all)} bytes")
        print(f"   🎯 Redução: {(1 - len(json_filtered)/len(json_all))*100:.1f}%")
        
        
        browser.close()
    
    print("\n" + "="*60)
    print("✅ Testes concluídos!")
    print("="*60)


def test_custom_zone():
    """Permite testar com zona personalizada"""
    
    from delnext_poc_playwright import DelnextPlaywrightPOC
    
    print("\n🔍 TESTE DE FILTRO PERSONALIZADO")
    print("="*60)
    
    # Configuração
    zona_desejada = input("Digite a zona para filtrar (ex: VianaCastelo): ").strip()
    data_consulta = input("Digite a data (ex: Feb 27, 2026) [Enter para padrão]: ").strip()
    
    if not data_consulta:
        data_consulta = "Feb 27, 2026"
    
    poc = DelnextPlaywrightPOC()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        if not poc.login(page):
            print("❌ Falha no login")
            browser.close()
            return
        
        print(f"\n🔍 Filtrando: {zona_desejada}")
        print(f"📅 Data: {data_consulta}")
        
        outbound = poc.scrape_outbound(
            page, 
            test_date=data_consulta,
            zone_filter=zona_desejada
        )
        
        print(f"\n📊 RESULTADO: {len(outbound)} entregas encontradas")
        
        if outbound:
            print("\n📦 Primeiras 5 entregas:")
            for i, item in enumerate(outbound[:5], 1):
                print(f"   {i}. {item['product_id']} - {item['customer_name']}")
                print(f"      {item['address']}, {item['postal_code']} {item['city']}")
                print(f"      Zona: {item['destination_zone']}")
                print()
            
            # Salvar resultado
            output_file = Path("debug_files/delnext_poc") / f"filtered_{zona_desejada.replace(' ', '_')}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(outbound, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Dados salvos em: {output_file}")
        else:
            print("\n⚠️ Nenhuma entrega encontrada para esta zona.")
            print("\n💡 Dicas:")
            print("   - Verifique se o nome da zona está correto")
            print("   - Tente sem filtro para ver zonas disponíveis:")
            print("     zone_filter=None")
        
        browser.close()


if __name__ == "__main__":
    import sys
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  TESTE DE FILTRO POR ZONA - POC DELNEXT                    ║
╚══════════════════════════════════════════════════════════════╝

Escolha uma opção:

1. Executar exemplos pré-configurados
   (VianaCastelo, Lisboa, Todas as zonas)

2. Testar com zona personalizada
   (você escolhe a zona)

3. Sair
    """)
    
    opcao = input("Opção (1-3): ").strip()
    
    if opcao == "1":
        print("\n🚀 Executando exemplos pré-configurados...\n")
        test_zone_filter_examples()
    
    elif opcao == "2":
        test_custom_zone()
    
    elif opcao == "3":
        print("\n👋 Até logo!")
        sys.exit(0)
    
    else:
        print("\n❌ Opção inválida")
        sys.exit(1)
