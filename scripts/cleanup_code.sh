#!/bin/bash
# Script de limpeza e formatação automática do código
# Sistema Leguas Franzinas - 01/03/2026

echo "🧹 Iniciando limpeza e formatação do código..."
echo ""

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Instalar ferramentas (se necessário)
echo "📦 Verificando ferramentas de formatação..."
pip install -q black autopep8 isort autoflake flake8

echo ""
echo "${YELLOW}⚠️  ATENÇÃO: Faça backup ou commit antes de continuar!${NC}"
read -p "Deseja continuar? (s/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[SsYy]$ ]]
then
    echo "${RED}❌ Cancelado pelo usuário${NC}"
    exit 1
fi

# 2. Contar problemas antes
echo ""
echo "📊 Contando problemas atuais..."
BEFORE=$(flake8 . 2>/dev/null | wc -l)
echo "   Problemas encontrados: ${RED}$BEFORE${NC}"

# 3. Remover imports não utilizados
echo ""
echo "${YELLOW}🗑️  Removendo imports não utilizados...${NC}"
find . -name "*.py" \
    -not -path "*/migrations/*" \
    -not -path "*/.venv/*" \
    -not -path "*/venv/*" \
    -not -path "*/env/*" \
    -not -path "*/staticfiles/*" \
    -not -path "*/media/*" \
    -not -path "*/__pycache__/*" \
    -exec autoflake --in-place --remove-all-unused-imports --remove-unused-variables {} \;

echo "   ${GREEN}✓ Imports não utilizados removidos${NC}"

# 4. Organizar imports
echo ""
echo "${YELLOW}📑 Organizando imports...${NC}"
isort . \
    --skip migrations \
    --skip .venv \
    --skip venv \
    --skip env \
    --skip staticfiles \
    --skip media \
    --profile black \
    --line-length 120

echo "   ${GREEN}✓ Imports organizados${NC}"

# 5. Formatar código com Black
echo ""
echo "${YELLOW}🎨 Formatando código com Black...${NC}"
black --line-length 120 \
    --exclude '(migrations|\.venv|venv|env|staticfiles|media|__pycache__)' \
    .

echo "   ${GREEN}✓ Código formatado${NC}"

# 6. Contar problemas depois
echo ""
echo "📊 Contando problemas após limpeza..."
AFTER=$(flake8 . 2>/dev/null | wc -l)
echo "   Problemas restantes: ${YELLOW}$AFTER${NC}"

# 7. Mostrar resultado
REDUCTION=$((BEFORE - AFTER))
PERCENT=$((REDUCTION * 100 / BEFORE))

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "${GREEN}✅ LIMPEZA CONCLUÍDA!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Antes:    ${RED}$BEFORE${NC} problemas"
echo "   Depois:   ${YELLOW}$AFTER${NC} problemas"
echo "   Redução:  ${GREEN}$REDUCTION${NC} problemas (${GREEN}$PERCENT%${NC})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 8. Listar principais problemas restantes
echo "🔍 Top 10 problemas restantes:"
flake8 . 2>/dev/null | grep -oE "[A-Z][0-9]+" | sort | uniq -c | sort -rn | head -10

echo ""
echo "💡 Dicas:"
echo "   - Revise as mudanças com: git diff"
echo "   - Teste a aplicação: docker-compose restart web"
echo "   - Para ver problemas: flake8 ."
echo ""
