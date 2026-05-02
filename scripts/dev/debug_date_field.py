"""
Script de Debug - Inspecionar Estrutura HTML do Datepicker
"""

from playwright.sync_api import sync_playwright
import time

def inspect_date_field():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--start-maximized'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        
        try:
            print("\n🔍 INSPEÇÃO DO CAMPO DE DATA")
            print("=" * 60)
            
            # Fazer login manual
            page.goto("https://www.delnext.com/admind/index.php", timeout=60000)
            
            print("\n👉 Faça login manualmente no navegador...")
            print("   Depois, aperte Enter aqui...")
            input()
            
            # Navegar para Outbound
            print("\n📤 Navegando para Outbound...")
            page.goto("https://www.delnext.com/admind/outbound_consult.php", timeout=60000)
            time.sleep(3)
            
            print("\n🔍 Executando JavaScript para inspecionar campos...")
            
            # Script para encontrar todos os inputs relacionados a data
            js_script = """
            () => {
                const results = [];
                
                // 1. Todos os inputs
                const inputs = document.querySelectorAll('input');
                inputs.forEach((input, index) => {
                    const info = {
                        index: index,
                        type: input.type,
                        name: input.name,
                        id: input.id,
                        class: input.className,
                        placeholder: input.placeholder,
                        readonly: input.readOnly,
                        value: input.value,
                        visible: input.offsetParent !== null
                    };
                    results.push({type: 'input', ...info});
                });
                
                // 2. Todos os selects
                const selects = document.querySelectorAll('select');
                selects.forEach((select, index) => {
                    const info = {
                        index: index,
                        name: select.name,
                        id: select.id,
                        class: select.className,
                        visible: select.offsetParent !== null
                    };
                    results.push({type: 'select', ...info});
                });
                
                // 3. Procurar elementos com texto "Date:"
                const labels = document.querySelectorAll('label, span, div');
                const dateElements = [];
                labels.forEach((el) => {
                    if (el.textContent.trim().toLowerCase().includes('date')) {
                        const nextElement = el.nextElementSibling;
                        if (nextElement) {
                            dateElements.push({
                                labelText: el.textContent.trim(),
                                nextTag: nextElement.tagName,
                                nextId: nextElement.id,
                                nextClass: nextElement.className
                            });
                        }
                    }
                });
                
                return {
                    inputs: results.filter(r => r.type === 'input'),
                    selects: results.filter(r => r.type === 'select'),
                    dateLabels: dateElements
                };
            }
            """
            
            result = page.evaluate(js_script)
            
            print("\n📋 INPUTS ENCONTRADOS:")
            print("-" * 60)
            for inp in result['inputs']:
                if inp['visible']:
                    print(f"\n  Input #{inp['index']}:")
                    print(f"    Type: {inp['type']}")
                    print(f"    Name: {inp['name']}")
                    print(f"    ID: {inp['id']}")
                    print(f"    Class: {inp['class']}")
                    print(f"    Placeholder: {inp['placeholder']}")
                    print(f"    ReadOnly: {inp['readonly']}")
                    print(f"    Value: {inp['value']}")
            
            print("\n\n📋 SELECTS ENCONTRADOS:")
            print("-" * 60)
            for sel in result['selects']:
                if sel['visible']:
                    print(f"\n  Select #{sel['index']}:")
                    print(f"    Name: {sel['name']}")
                    print(f"    ID: {sel['id']}")
                    print(f"    Class: {sel['class']}")
            
            print("\n\n📋 ELEMENTOS COM 'DATE':")
            print("-" * 60)
            for de in result['dateLabels']:
                print(f"\n  Label: '{de['labelText']}'")
                print(f"    Next: <{de['nextTag']}> id='{de['nextId']}' class='{de['nextClass']}'")
            
            print("\n\n💡 TESTE MANUAL:")
            print("=" * 60)
            print("O navegador permanecerá aberto.")
            print("Você pode:")
            print("  1. Clicar manualmente no campo de data")
            print("  2. Abrir o DevTools (F12)")
            print("  3. Inspecionar o elemento")
            print("  4. Copiar o seletor CSS")
            print("\nQuando terminar, aperte Enter para fechar...")
            input()
            
        except Exception as e:
            print(f"\n❌ Erro: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            browser.close()


if __name__ == "__main__":
    inspect_date_field()
