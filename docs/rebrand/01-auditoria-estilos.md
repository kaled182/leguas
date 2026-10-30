# Auditoria de estilos — baseline

**Estado:** Fase 0. Análise estática de 221 ficheiros `.html`, `.css` e `.js`, com commit `469a7d8`.

## 1. Resumo

| Métrica | Valor | Meta do briefing |
|---|---|---|
| Cores hardcoded distintas (hex, rgb, rgba) | 172 | 0 fora de `tokens.css` |
| Ocorrências de cores hardcoded | 723 | 0 fora de `tokens.css` |
| Cores da marca presentes | 2 de 14 | 14 |
| Classes de cor Tailwind nos templates | 27568 | Só tokens |
| Famílias de cor Tailwind | 19 | Roxo, laranja, neutros e 3 estados |
| Tamanhos de fonte distintos | 46 | Escala única |
| Valores de raio distintos | 24 | Escala única |
| Valores de sombra distintos | 40 | Escala única |
| Atributos `style=""` no código | 177 em 32 ficheiros | 0 |
| Emojis nos templates | 267 em 48 ficheiros | 0 em títulos e chips |
| Gradientes | 196 em 95 ficheiros | Só login e Modo ecrã |
| `console.log` e `console.debug` | 31 em 7 ficheiros | 0 em produção |
| Valores antigos `#4A1A6B` e `#F59000` | 0 | 0 |
| Bases de layout | 10 | 1 shell interno, portais separados |
| Páginas HTML sem base (`<html>` próprio) | 20 | Só as bases |

## 2. Tailwind e configuração

- `tailwind.config` está inline e duplicado em `templates/layouts/admin_base.html:37` e `settlements/templates/settlements/base.html:33`.
- O `primary` do projeto é azul (`#2563eb`). A marca usa roxo.
- `theme/tailwind.config.js` tem `extend: {}`. Não define tokens.
- `theme/package.json` fixa `tailwindcss ^3.3.2`. `dashboard_leguas/base.html:8` carrega `@tailwindcss/browser@4`. São 2 versões maiores diferentes.
- O CDN `cdn.tailwindcss.com` está em 14 templates. O critério de aceitação cobre este domínio, mas a Fase 1 tem de cobrir também o `@tailwindcss/browser@4`.

## 3. Componentes duplicados

### Cabeçalhos de página

O briefing indica 5 padrões. O código tem **19 variantes de hero gradiente** e 5 outros padrões.

| Padrão | Templates |
|---|---|
| Sem h1 | 50 |
| Título com ícone | 45 |
| Título com ícone em card | 15 |
| Título solto | 14 |
| Hero gradiente teal→teal | 8 |
| Hero gradiente indigo→pink | 5 |
| Hero gradiente purple→purple | 5 |
| Hero gradiente purple→pink | 4 |
| Hero gradiente blue→blue | 4 |
| Hero gradiente indigo→purple | 4 |
| Hero gradiente amber→orange | 3 |
| Hero gradiente orange→red | 3 |
| Hero gradiente emerald→green | 2 |
| Hero gradiente violet→purple | 2 |
| Hero gradiente blue→indigo | 2 |
| Hero gradiente red→orange | 1 |
| Hero gradiente yellow→yellow | 1 |
| Hero gradiente emerald→cyan | 1 |
| Hero gradiente primary→primary | 1 |
| Hero gradiente violet→violet | 1 |
| Título com emoji | 1 |
| Hero gradiente emerald→teal | 1 |
| Hero gradiente rose→amber | 1 |
| Hero gradiente emerald→emerald | 1 |

### Cards

Existem **321 combinações distintas** de classes para cards (fundo, raio, borda e padding), depois de retirar variantes `dark:` e `hover:`.

| Classes | Usos |
|---|---|
| `bg-white border border-gray-200/50 p-4 rounded-xl` | 52 |
| `bg-white border border-gray-200/50 p-6 rounded-xl shadow-sm slide-in` | 51 |
| `bg-white border border-gray-200 p-4 rounded-xl` | 36 |
| `bg-white border border-gray-200/50 p-6 rounded-xl shadow-sm` | 34 |
| `bg-white border border-gray-200/50 fade-in p-6 rounded-xl shadow-sm` | 29 |
| `bg-white border border-gray-200/50 p-6 rounded-xl scale-in shadow-sm` | 19 |
| `bg-white border border-gray-200 p-3 rounded-lg` | 17 |
| `bg-rose-50 border border-rose-200/50 p-4 rounded-xl` | 12 |
| `bg-white border border-gray-200/50 p-5 rounded-2xl shadow-sm` | 11 |
| `bg-white border border-gray-200 p-4 rounded-xl shadow-sm` | 11 |
| `bg-white p-3 rounded-lg shadow-sm` | 10 |
| `bg-amber-50 border border-amber-200/50 p-4 rounded-xl` | 10 |

### Botões primários por cor de fundo

| Cor | Usos |
|---|---|
| gray | 575 |
| indigo | 121 |
| emerald | 110 |
| blue | 55 |
| amber | 42 |
| purple | 41 |
| rose | 40 |
| orange | 25 |
| red | 24 |
| violet | 22 |
| teal | 17 |
| green | 14 |
| yellow | 7 |
| primary | 5 |
| slate | 3 |
| sky | 2 |
| cyan | 2 |
| pink | 1 |

### Badges

Existem **90 combinações distintas** de classes para badges.

### Layouts

| Base | Páginas |
|---|---|
| `settlements/base.html` | 88 |
| `layouts/admin_base.html` | 27 |
| `drivers_app/portal/_base.html` | 19 |
| `settlements/portal_empresa/_base.html` | 8 |
| `base.html` | 4 |
| `management/base.html` | 1 |
| `dashboard_leguas/base.html` | 1 |
| `customauth/base_driver.html` | 1 |
| `base-login.html` | 1 |
| `settlements/portal_empresa/_layout.html` | 1 |

Menus: `layouts/partials/sidebar.html` (57 ligações), `dashboard_sidebar.html` (30), `partials/sidebar_links.html` (11).

## 4. Moeda e formatos

- Valores com `€` antes do número: 430 ocorrências em templates. Com `€` depois: 23.
- `floatformat:2` tem 363 usos. `intcomma` e `humanize` têm 0 usos. Por isso, os milhares não têm separador.
- `pluralize` tem 60 usos. Há 24 ocorrências de plural forçado, como `integração(ões)`.
- **Decisão técnica para a Fase 1:** criar 1 filtro `|eur`, testado, em vez de alterar cada cálculo. O filtro muda só a apresentação.

## 5. Famílias de cor Tailwind

| Família | Classes |
|---|---|
| gray | 15567 |
| emerald | 2074 |
| amber | 1596 |
| blue | 1401 |
| rose | 1242 |
| red | 1174 |
| indigo | 1157 |
| purple | 903 |
| violet | 623 |
| orange | 524 |
| teal | 372 |
| green | 240 |
| primary | 228 |
| yellow | 187 |
| slate | 91 |
| sky | 78 |
| cyan | 42 |
| pink | 37 |
| fuchsia | 32 |

## 6. Tipografia

| Tamanho | Usos |
|---|---|
| `tw:text-xs` | 3022 |
| `tw:text-sm` | 2785 |
| `tw:text-2xl` | 356 |
| `tw:text-lg` | 211 |
| `tw:text-3xl` | 116 |
| `tw:text-xl` | 98 |
| `tw:text-base` | 93 |
| `0.875rem` | 17 |
| `0.7rem` | 15 |
| `10px` | 11 |
| `11px` | 10 |
| `tw:text-4xl` | 10 |
| `0.75rem` | 8 |
| `9px` | 6 |
| `1rem` | 5 |
| `12px` | 4 |
| `13px` | 4 |
| `11.5px` | 3 |
| `7.5pt` | 3 |
| `8.4pt` | 3 |
| `8pt` | 3 |
| `7pt` | 3 |
| `0.85rem` | 2 |
| `12.5px` | 2 |
| `7.6pt` | 2 |
| `0.65rem` | 1 |
| `22px` | 1 |
| `18px` | 1 |
| `14px` | 1 |
| `13.5px` | 1 |
| `9pt` | 1 |
| `6pt` | 1 |
| `15pt` | 1 |
| `8.8pt` | 1 |
| `6.4pt` | 1 |
| `8.1pt` | 1 |
| `6.8pt` | 1 |
| `11pt` | 1 |
| `10.5px` | 1 |
| `7.8pt` | 1 |
| `2rem` | 1 |
| `1.2rem` | 1 |
| `tw:text-5xl` | 1 |
| `0.8rem` | 1 |
| `1.875rem` | 1 |
| `1.05em` | 1 |

**Famílias de letra:** `Inter` (11); `monospace` (7); `'Inter', sans-serif` (6); `inherit` (3); `Poppins` (2); `'Inter', 'Segoe UI', Arial, sans-serif` (2); `'Poppins',sans-serif` (1); `'Segoe UI', 'Roboto', Arial, sans-serif` (1); `'Inter', Arial, sans-serif` (1).

## 7. Raios

| Valor | Usos |
|---|---|
| `tw:rounded-lg` | 1984 |
| `tw:rounded` | 839 |
| `tw:rounded-xl` | 835 |
| `tw:rounded-full` | 349 |
| `tw:rounded-2xl` | 165 |
| `tw:rounded-md` | 107 |
| `0.5rem` | 20 |
| `9999px` | 20 |
| `tw:rounded-sm` | 13 |
| `50%` | 9 |
| `4px` | 7 |
| `0.75rem` | 6 |
| `8px` | 6 |
| `3px` | 4 |
| `0.375rem` | 3 |
| `6px` | 3 |
| `tw:rounded-3xl` | 2 |
| `25px` | 1 |
| `0.4rem` | 1 |
| `10px` | 1 |
| `2.5mm` | 1 |
| `3.5mm` | 1 |
| `0` | 1 |
| `1rem` | 1 |

## 8. Sombras

| Valor | Usos |
|---|---|
| `tw:shadow-sm` | 365 |
| `tw:shadow` | 121 |
| `tw:shadow-lg` | 120 |
| `tw:shadow-2xl` | 83 |
| `tw:shadow-md` | 64 |
| `tw:shadow-xl` | 24 |
| `none` | 3 |
| `tw:shadow-none` | 2 |
| `0 2px 8px rgba(0,0,0,0.04)` | 2 |
| `0 2px 6px rgba(0,0,0,.3)` | 2 |
| `0 1px 3px rgba(0,0,0,.3)` | 2 |
| `0 2px 4px rgba(0,0,0,.3)` | 2 |
| `0 1px 2px rgba(0,0,0,.4)` | 2 |
| `inset 0 1px 4px rgba(0,0,0,.3)` | 1 |
| `inset 0 0 20px rgba(255,255,255,.35)` | 1 |
| `0 0 6px rgba(0,0,0,.5)` | 1 |
| `0 0 0 2px #6366f1 inset` | 1 |
| `0 8px 30px rgba(0,0,0,.45)` | 1 |
| `0 0 0 2px #f97316 inset` | 1 |
| `0 8px 20px rgba(102, 126, 234, 0.1)` | 1 |
| `0 10px 25px rgba(102, 126, 234, 0.1)` | 1 |
| `0 10px 25px rgba(102, 126, 234, 0.3)` | 1 |
| `0 4px 16px rgba(0,0,0,0.08)` | 1 |
| `0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, ` | 1 |
| `0 0 5px rgba(34, 197, 94, 0.5)` | 1 |
| `0 0 20px rgba(34, 197, 94, 0.8)` | 1 |
| `0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0` | 1 |
| `0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0` | 1 |
| `0 4px 12px rgba(0, 0, 0, 0.1)` | 1 |
| `0 4px 12px rgba(0, 0, 0, 0.3)` | 1 |
| `0 1px 3px rgba(0, 0, 0, 0.12),
    0 1px 2px rgba(0, 0, 0, 0` | 1 |
| `0 14px 28px rgba(0, 0, 0, 0.25),
    0 10px 10px rgba(0, 0, ` | 1 |
| `0 1px 3px rgba(0, 0, 0, 0.5),
    0 1px 2px rgba(0, 0, 0, 0.` | 1 |
| `0 14px 28px rgba(0, 0, 0, 0.7),
    0 10px 10px rgba(0, 0, 0` | 1 |
| `tw:shadow-inner` | 1 |
| `0 0 0 3px rgba(59, 130, 246, 0.1)` | 1 |
| `0 2px 8px rgba(99, 102, 241, 0.08)` | 1 |
| `0 4px 12px rgba(0,0,0,0.15)` | 1 |
| `0 4px 12px rgba(0, 0, 0, 0.15)` | 1 |
| `0 2px 6px rgba(0,0,0,.4)` | 1 |

## 9. Ficheiros com mais `style=""`, emojis e `console.log`

| Ficheiro | `style=""` |
|---|---|
| `settlements/templates/settlements/pre_invoice_admin_list.html` | 60 |
| `accounting/templates/accounting/break_even.html` | 25 |
| `core/templates/core/partner_detail.html` | 16 |
| `accounting/templates/accounting/executive_dashboard.html` | 13 |
| `settlements/templates/settlements/cainiao_map.html` | 12 |
| `dashboard_leguas/templates/dashboard_leguas/home.html` | 6 |
| `converter/templates/converter_table.html` | 5 |
| `drivers_app/templates/drivers_app/driver_public_register_full.html` | 4 |
| `drivers_app/templates/drivers_app/portal/dashboard.html` | 4 |
| `contracts/templates/contracts/generator.html` | 3 |
| `settlements/templates/settlements/cainiao_map_compare.html` | 3 |
| `accounting/templates/accounting/fornecedor_list.html` | 2 |
| `drivers_app/templates/drivers_app/empresas_parceiras.html` | 2 |
| `drivers_app/templates/drivers_app/admin/drivers_central.html` | 2 |
| `settlements/templates/settlements/portal_empresa/reports.html` | 2 |

| Ficheiro | Emojis |
|---|---|
| `core/templates/core/partner_detail.html` | 78 |
| `system_config/templates/system_config/config.html` | 30 |
| `settlements/templates/settlements/pre_invoice_admin_list.html` | 19 |
| `settlements/templates/settlements/cainiao_packages.html` | 18 |
| `drivers_app/templates/drivers_app/admin_complaints.html` | 9 |
| `drivers_app/templates/drivers_app/empresas_parceiras.html` | 9 |
| `settlements/templates/settlements/cainiao_map.html` | 9 |
| `settlements/templates/settlements/drivers_rank.html` | 9 |
| `settlements/templates/settlements/cainiao_waybill_detail.html` | 8 |
| `settlements/templates/settlements/partials/cainiao_billing_reconciliation.html` | 6 |
| `drivers_app/templates/drivers_app/portal/admin_complaints.html` | 5 |
| `accounting/templates/accounting/break_even.html` | 4 |
| `management/templates/management/base.html` | 4 |
| `settlements/templates/settlements/pudo_fake_delivery_suspects.html` | 4 |
| `settlements/templates/settlements/shareholder_dashboard.html` | 4 |

| Ficheiro | `console.log` |
|---|---|
| `system_config/templates/system_config/whatsapp_dashboard.html` | 11 |
| `management/static/management/js/main.js` | 7 |
| `static/js/sidebar.js` | 6 |
| `management/templates/management/base.html` | 3 |
| `drivers_app/templates/drivers_app/empresas_parceiras.html` | 2 |
| `accounting/templates/accounting/bill_form.html` | 1 |
| `deploy/wppconnect/patch.js` | 1 |

## 10. Todas as cores hardcoded

| Cor | Usos | Marca | Ficheiros principais |
|---|---|---|---|
| `#ffffff` | 75 | não | `contracts/static/contracts/generator.css` (14), `static/css/base.css` (5), `accounting/templates/accounting/fornecedor_form.html` (3) |
| `#374151` | 38 | não | `accounting/templates/accounting/audit_timeline.html` (3), `accounting/templates/accounting/fornecedor_form.html` (2), `accounting/templates/accounting/plano_detail.html` (2) |
| `#e5e7eb` | 37 | não | `management/static/management/js/main.js` (6), `accounting/templates/accounting/plano_detail.html` (4), `accounting/templates/accounting/executive_dashboard.html` (4) |
| `#1f2937` | 36 | não | `accounting/templates/accounting/break_even.html` (3), `payroll/templates/payroll/payroll_detail.html` (3), `accounting/templates/accounting/fornecedor_form.html` (2) |
| `#d1d5db` | 25 | não | `payroll/templates/payroll/payroll_detail.html` (2), `management/static/management/js/main.js` (2), `accounting/templates/accounting/bill_form.html` (1) |
| `#6b7280` | 23 | não | `accounting/templates/accounting/executive_dashboard.html` (4), `settlements/templates/settlements/cainiao_map.html` (2), `accounting/templates/accounting/fornecedor_form.html` (1) |
| `#10b981` | 19 | não | `accounting/templates/accounting/break_even.html` (4), `drivers_app/templates/drivers_app/admin/drivers_central.html` (4), `settlements/templates/settlements/cainiao_map.html` (2) |
| `#6366f1` | 17 | não | `static/css/base.css` (3), `customauth/static/customauth/css/auth.css` (3), `settlements/templates/settlements/cainiao_map.html` (2) |
| `#065f46` | 15 | não | `accounting/templates/accounting/audit_timeline.html` (3), `accounting/templates/accounting/bank_reconciliation.html` (2), `accounting/templates/accounting/imposto_list.html` (1) |
| `#d1fae5` | 14 | não | `accounting/templates/accounting/audit_timeline.html` (2), `accounting/templates/accounting/plano_detail.html` (2), `accounting/templates/accounting/bank_reconciliation.html` (2) |
| `#4f46e5` | 14 | não | `settlements/templates/settlements/cainiao_map.html` (9), `static/css/base.css` (3), `customauth/static/customauth/css/auth.css` (2) |
| `#9ca3af` | 13 | não | `accounting/templates/accounting/executive_dashboard.html` (4), `accounting/templates/accounting/plano_detail.html` (2), `templates/layouts/partials/sidebar.html` (2) |
| `#92400e` | 12 | não | `accounting/templates/accounting/imposto_list.html` (1), `accounting/templates/accounting/audit_timeline.html` (1), `accounting/templates/accounting/plano_detail.html` (1) |
| `#fee2e2` | 12 | não | `accounting/templates/accounting/audit_timeline.html` (2), `accounting/templates/accounting/plano_detail.html` (2), `accounting/templates/accounting/imposto_list.html` (1) |
| `#fef3c7` | 11 | não | `accounting/templates/accounting/plano_detail.html` (2), `accounting/templates/accounting/imposto_list.html` (1), `accounting/templates/accounting/category_list.html` (1) |
| `#991b1b` | 11 | não | `accounting/templates/accounting/audit_timeline.html` (2), `accounting/templates/accounting/imposto_list.html` (1), `accounting/templates/accounting/plano_detail.html` (1) |
| `#dc2626` | 10 | não | `accounting/templates/accounting/fornecedor_form.html` (1), `accounting/templates/accounting/dre.html` (1), `accounting/templates/accounting/break_even.html` (1) |
| `#059669` | 10 | não | `settlements/templates/settlements/cainiao_map.html` (5), `accounting/templates/accounting/dre.html` (1), `accounting/templates/accounting/break_even.html` (1) |
| `#ef4444` | 10 | não | `accounting/templates/accounting/break_even.html` (3), `accounting/templates/accounting/audit_timeline.html` (1), `accounting/templates/accounting/plano_detail.html` (1) |
| `#f9fafb` | 10 | não | `payroll/templates/payroll/payroll_detail.html` (3), `payroll/templates/payroll/employee_form.html` (2), `payroll/templates/payroll/payroll_list.html` (2) |
| `#4b5563` | 9 | não | `management/static/management/js/main.js` (6), `accounting/templates/accounting/executive_dashboard.html` (1), `templates/layouts/partials/sidebar.html` (1) |
| `#e0e7ff` | 9 | não | `static/css/base.css` (5), `drivers_app/static/driversmanager/css/folium-map.css` (2), `accounting/templates/accounting/hub.html` (1) |
| `#111827` | 8 | não | `accounting/templates/accounting/executive_dashboard.html` (2), `payroll/templates/payroll/payroll_detail.html` (2), `accounting/templates/accounting/hub.html` (1) |
| `rgba(0,0,0,.3)` | 7 | não | `settlements/templates/settlements/cainiao_map.html` (5), `accounting/templates/accounting/break_even.html` (1), `settlements/templates/settlements/cainiao_map_compare.html` (1) |
| `#1e40af` | 7 | não | `accounting/templates/accounting/audit_timeline.html` (1), `accounting/templates/accounting/category_list.html` (1), `accounting/templates/accounting/bank_reconciliation.html` (1) |
| `#9d174d` | 7 | não | `accounting/templates/accounting/audit_timeline.html` (1), `accounting/templates/accounting/category_list.html` (1), `accounting/templates/accounting/bill_detail.html` (1) |
| `#667eea` | 7 | não | `drivers_app/templates/drivers_app/driver_public_register_full.html` (3), `drivers_app/templates/drivers_app/driver_public_register.html` (2), `customauth/static/customauth/css/auth.css` (2) |
| `#dbeafe` | 6 | não | `accounting/templates/accounting/category_list.html` (1), `accounting/templates/accounting/bank_reconciliation.html` (1), `accounting/templates/accounting/cost_center_list.html` (1) |
| `#fce7f3` | 6 | não | `accounting/templates/accounting/category_list.html` (1), `accounting/templates/accounting/bill_detail.html` (1), `accounting/templates/accounting/bill_list.html` (1) |
| `#f59e0b` | 5 | não | `accounting/templates/accounting/break_even.html` (1), `accounting/templates/accounting/plano_detail.html` (1), `drivers_app/templates/drivers_app/admin/drivers_central.html` (1) |
| `#5b21b6` | 5 | não | `accounting/templates/accounting/category_list.html` (1), `accounting/templates/accounting/bill_detail.html` (1), `accounting/templates/accounting/bill_list.html` (1) |
| `#c9b8d9` | 5 | não | `contracts/static/contracts/generator.css` (4), `contracts/static/contracts/generator.js` (1) |
| `#764ba2` | 5 | não | `drivers_app/templates/drivers_app/driver_public_register.html` (2), `customauth/static/customauth/css/auth.css` (2), `drivers_app/templates/drivers_app/driver_public_register_full.html` (1) |
| `rgba(0,0,0,0.1)` | 5 | não | `static/css/modern-dashboard.css` (2), `customauth/templates/customauth/driver_dashboard.html` (2), `static/css/base.css` (1) |
| `rgba(0,0,0,0.05)` | 4 | não | `management/static/management/js/main.js` (2), `accounting/templates/accounting/dre.html` (1), `static/css/base.css` (1) |
| `#8b5cf6` | 4 | não | `drivers_app/templates/drivers_app/admin/payments.html` (2), `accounting/templates/accounting/plano_detail.html` (1), `accounting/templates/accounting/plano_list.html` (1) |
| `#ede9fe` | 4 | não | `accounting/templates/accounting/category_list.html` (1), `accounting/templates/accounting/bill_detail.html` (1), `accounting/templates/accounting/bill_list.html` (1) |
| `rgba(99,102,241,0.1)` | 4 | não | `accounting/templates/accounting/treasury_dashboard.html` (1), `templates/layouts/partials/sidebar.html` (1), `static/css/modern-dashboard.css` (1) |
| `rgba(255,255,255,0.08)` | 4 | não | `dashboard_leguas/templates/dashboard_leguas/home.html` (2), `drivers_app/templates/drivers_app/admin/payments.html` (1), `drivers_app/templates/drivers_app/admin/drivers_central.html` (1) |
| `rgba(0,0,0,0.06)` | 4 | não | `dashboard_leguas/templates/dashboard_leguas/home.html` (2), `drivers_app/templates/drivers_app/admin/payments.html` (1), `drivers_app/templates/drivers_app/admin/drivers_central.html` (1) |
| `rgba(255,255,255,0.1)` | 4 | não | `management/static/management/js/main.js` (2), `customauth/templates/customauth/driver_dashboard.html` (2) |
| `rgba(99,102,241,0.05)` | 3 | não | `accounting/templates/accounting/dre.html` (1), `accounting/templates/accounting/bank_reconciliation.html` (1), `static/css/modern-dashboard.css` (1) |
| `#3b82f6` | 3 | não | `accounting/templates/accounting/break_even.html` (1), `static/css/modern-dashboard.css` (1), `settlements/templates/settlements/cainiao_map_compare.html` (1) |
| `#3730a3` | 3 | não | `accounting/templates/accounting/audit_timeline.html` (2), `accounting/templates/accounting/hub.html` (1) |
| `#047857` | 3 | não | `accounting/templates/accounting/audit_timeline.html` (1), `accounting/templates/accounting/executive_dashboard.html` (1), `static/css/modern-dashboard.css` (1) |
| `#4338ca` | 3 | não | `templates/layouts/partials/sidebar.html` (2), `accounting/templates/accounting/executive_dashboard.html` (1) |
| `rgba(255,255,255,.1)` | 3 | não | `contracts/static/contracts/generator.css` (3) |
| `#2563eb` | 3 | não | `drivers_app/static/driversmanager/css/folium-map.css` (3) |
| `#c7d2fe` | 3 | não | `templates/layouts/partials/sidebar.html` (2), `customauth/static/customauth/css/auth.css` (1) |
| `rgba(99,102,241,0.15)` | 3 | não | `templates/layouts/partials/sidebar.html` (3) |
| `#18181b` | 3 | não | `static/css/base.css` (3) |
| `#f1f5f9` | 3 | não | `static/css/modern-dashboard.css` (2), `static/css/base.css` (1) |
| `rgba(0,0,0,0.04)` | 3 | não | `static/css/base.css` (2), `static/css/modern-dashboard.css` (1) |
| `rgba(0,0,0,.4)` | 3 | não | `settlements/templates/settlements/cainiao_map_compare.html` (2), `settlements/templates/settlements/cainiao_waybill_detail.html` (1) |
| `rgba(255,255,255,.35)` | 2 | não | `accounting/templates/accounting/break_even.html` (1), `contracts/static/contracts/generator.css` (1) |
| `rgba(0,0,0,.5)` | 2 | não | `accounting/templates/accounting/break_even.html` (2) |
| `rgba(16,185,129,0.15)` | 2 | não | `accounting/templates/accounting/break_even.html` (1), `dashboard_leguas/templates/dashboard_leguas/home.html` (1) |
| `#f3f4f6` | 2 | não | `accounting/templates/accounting/audit_timeline.html` (1), `accounting/templates/accounting/executive_dashboard.html` (1) |
| `#b91c1c` | 2 | não | `accounting/templates/accounting/executive_dashboard.html` (1), `static/css/modern-dashboard.css` (1) |
| `rgb(16,185,129)` | 2 | não | `accounting/templates/accounting/treasury_dashboard.html` (2) |
| `rgb(244,63,94)` | 2 | não | `accounting/templates/accounting/treasury_dashboard.html` (2) |
| `#2e0a3e` | 2 | sim | `contracts/static/contracts/generator.css` (2) |
| `#4a1a63` | 2 | não | `contracts/static/contracts/generator.css` (2) |
| `#241033` | 2 | não | `contracts/static/contracts/generator.css` (2) |
| `#b23a30` | 2 | não | `contracts/static/contracts/generator.js` (2) |
| `#f97316` | 2 | não | `drivers_app/templates/drivers_app/admin_tickets_cainiao.html` (2) |
| `#eef2ff` | 2 | não | `drivers_app/templates/drivers_app/driver_public_register_full.html` (1), `static/css/base.css` (1) |
| `rgba(102,126,234,0.1)` | 2 | não | `drivers_app/templates/drivers_app/driver_public_register_full.html` (1), `drivers_app/templates/drivers_app/driver_public_register.html` (1) |
| `#0ea5e9` | 2 | não | `drivers_app/templates/drivers_app/admin/payments.html` (2) |
| `rgba(99,102,241,0.25)` | 2 | não | `drivers_app/templates/drivers_app/admin/drivers_central.html` (1), `templates/layouts/partials/sidebar.html` (1) |
| `rgba(99,102,241,0.2)` | 2 | não | `management/static/management/js/main.js` (2) |
| `rgba(99,102,241,1)` | 2 | não | `management/static/management/js/main.js` (2) |
| `rgba(209,213,219,0.2)` | 2 | não | `management/static/management/js/main.js` (2) |
| `rgba(156,163,175,1)` | 2 | não | `management/static/management/js/main.js` (2) |
| `rgba(99,102,241,0.08)` | 2 | não | `templates/layouts/partials/sidebar.html` (1), `customauth/static/customauth/css/auth.css` (1) |
| `#27272a` | 2 | não | `static/css/base.css` (2) |
| `#312e81` | 2 | não | `static/css/base.css` (2) |
| `#a5b4fc` | 2 | não | `static/css/base.css` (2) |
| `#232136` | 2 | não | `static/css/base.css` (2) |
| `#22223b` | 2 | não | `static/css/base.css` (2) |
| `#cbd5e1` | 2 | não | `static/css/modern-dashboard.css` (2) |
| `#475569` | 2 | não | `static/css/modern-dashboard.css` (2) |
| `#1e293b` | 2 | não | `static/css/modern-dashboard.css` (2) |
| `#64748b` | 2 | não | `static/css/modern-dashboard.css` (1), `settlements/templates/settlements/cainiao_map_compare.html` (1) |
| `rgba(0,0,0,0.3)` | 2 | não | `static/css/modern-dashboard.css` (2) |
| `rgba(0,0,0,0.12)` | 2 | não | `static/css/modern-dashboard.css` (1), `core/templates/core/partner_detail.html` (1) |
| `rgba(0,0,0,0.6)` | 2 | não | `static/css/modern-dashboard.css` (2) |
| `rgba(0,0,0,0.15)` | 2 | não | `customauth/static/customauth/css/auth.css` (2) |
| `rgba(79,70,229,.85)` | 2 | não | `settlements/templates/settlements/cainiao_map.html` (1), `settlements/templates/settlements/cainiao_map_compare.html` (1) |
| `#f43f5e` | 1 | não | `accounting/templates/accounting/dre.html` (1) |
| `rgba(255,255,255,0.05)` | 1 | não | `accounting/templates/accounting/dre.html` (1) |
| `rgba(16,185,129,0.1)` | 1 | não | `accounting/templates/accounting/dre.html` (1) |
| `rgba(244,63,94,0.1)` | 1 | não | `accounting/templates/accounting/dre.html` (1) |
| `rgba(255,255,255,.7)` | 1 | não | `accounting/templates/accounting/break_even.html` (1) |
| `#0e7490` | 1 | não | `accounting/templates/accounting/audit_timeline.html` (1) |
| `#1e1b4b` | 1 | não | `accounting/templates/accounting/executive_dashboard.html` (1) |
| `rgba(99,102,241,0.85)` | 1 | não | `accounting/templates/accounting/executive_dashboard.html` (1) |
| `rgba(244,63,94,0.07)` | 1 | não | `accounting/templates/accounting/cash_flow.html` (1) |
| `#ccfbf1` | 1 | não | `accounting/templates/accounting/hub.html` (1) |
| `#115e59` | 1 | não | `accounting/templates/accounting/hub.html` (1) |
| `#fecaca` | 1 | não | `accounting/templates/accounting/hub.html` (1) |
| `#7f1d1d` | 1 | não | `accounting/templates/accounting/hub.html` (1) |
| `rgba(16,185,129,${a})` | 1 | não | `accounting/templates/accounting/hub.html` (1) |
| `rgba(239,68,68,${a})` | 1 | não | `accounting/templates/accounting/hub.html` (1) |
| `rgb(99,102,241)` | 1 | não | `accounting/templates/accounting/treasury_dashboard.html` (1) |
| `#dcfce7` | 1 | não | `accounting/templates/accounting/cost_center_list.html` (1) |
| `#166534` | 1 | não | `accounting/templates/accounting/cost_center_list.html` (1) |
| `#ddd6fe` | 1 | não | `accounting/templates/accounting/fornecedor_list.html` (1) |
| `#5b2178` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#f7941d` | 1 | sim | `contracts/static/contracts/generator.css` (1) |
| `#2d2438` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#6b6175` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#f5f2f8` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#e4dcec` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#31123f` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#eeeeee` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#9d8bb0` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#3a2748` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#fdf1e0` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#6b2438` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#e8ddf2` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#ffd9a8` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#b7f3d6` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `rgba(255,255,255,.05)` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `rgba(255,255,255,.18)` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `rgba(0,0,0,.45)` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `rgba(247,148,29,.15)` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `rgba(247,148,29,.5)` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `rgba(16,185,129,.15)` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `rgba(16,185,129,.5)` | 1 | não | `contracts/static/contracts/generator.css` (1) |
| `#ffb27a` | 1 | não | `contracts/static/contracts/generator.js` (1) |
| `rgba(148,163,184,0.30)` | 1 | não | `drivers_app/templates/drivers_app/admin_complaints.html` (1) |
| `rgba(148,163,184,0.55)` | 1 | não | `drivers_app/templates/drivers_app/admin_complaints.html` (1) |
| `rgba(148,163,184,0.35)` | 1 | não | `drivers_app/templates/drivers_app/admin_complaints.html` (1) |
| `rgba(148,163,184,.30)` | 1 | não | `drivers_app/templates/drivers_app/admin_tickets_cainiao.html` (1) |
| `rgba(249,115,22,.08)` | 1 | não | `drivers_app/templates/drivers_app/admin_tickets_cainiao.html` (1) |
| `#cbd5e0` | 1 | não | `drivers_app/templates/drivers_app/driver_public_register_full.html` (1) |
| `#f7fafc` | 1 | não | `drivers_app/templates/drivers_app/driver_public_register_full.html` (1) |
| `rgba(102,126,234,0.3)` | 1 | não | `drivers_app/templates/drivers_app/driver_public_register.html` (1) |
| `#14b8a6` | 1 | não | `drivers_app/templates/drivers_app/admin/payments.html` (1) |
| `#34d399` | 1 | não | `drivers_app/templates/drivers_app/admin/drivers_central.html` (1) |
| `rgba(129,140,248,0.35)` | 1 | não | `drivers_app/templates/drivers_app/admin/drivers_central.html` (1) |
| `#f0f4ff` | 1 | não | `drivers_app/static/driversmanager/css/folium-map.css` (1) |
| `rgba(59,130,246,0.08)` | 1 | não | `drivers_app/static/driversmanager/css/folium-map.css` (1) |
| `#000000` | 1 | não | `management/templates/management/tools/qr_generator.html` (1) |
| `#818cf8` | 1 | não | `static/css/base.css` (1) |
| `#7c3aed` | 1 | não | `static/css/base.css` (1) |
| `#f8fafc` | 1 | não | `static/css/base.css` (1) |
| `#1a1a2e` | 1 | não | `static/css/base.css` (1) |
| `rgba(0,0,0,0.08)` | 1 | não | `static/css/base.css` (1) |
| `rgba(156,163,175,0.5)` | 1 | não | `static/css/base.css` (1) |
| `#94a3b8` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `#1d4ed8` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `#d97706` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `#1e3a8a` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `#b45309` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(34,197,94,0.5)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(34,197,94,0.8)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(0,0,0,0.2)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(168,85,247,0.05)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(168,85,247,0.1)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(0,0,0,0.24)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(0,0,0,0.25)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(0,0,0,0.22)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(0,0,0,0.5)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `rgba(0,0,0,0.7)` | 1 | não | `static/css/modern-dashboard.css` (1) |
| `#222222` | 1 | não | `customauth/static/customauth/css/auth.css` (1) |
| `rgba(255,255,255,0.95)` | 1 | não | `customauth/static/customauth/css/auth.css` (1) |
| `rgba(255,255,255,0.2)` | 1 | não | `customauth/static/customauth/css/auth.css` (1) |
| `rgba(59,130,246,0.1)` | 1 | não | `customauth/static/customauth/css/auth.css` (1) |
| `rgba(99,102,241,.3)` | 1 | não | `settlements/templates/settlements/cainiao_map.html` (1) |
| `rgba(99,102,241,.9)` | 1 | não | `settlements/templates/settlements/cainiao_map.html` (1) |
