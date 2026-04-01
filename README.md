# 💰 LifeOS - Gestão Financeira Inteligente (MVP)

Sistema Fullstack responsivo focado em **integridade de dados** e **alta disponibilidade**. Desenvolvido para centralizar o controle de gastos e contas a pagar com uma experiência *mobile-first*.

---

## 🏗️ 1. Arquitetura do Ecossistema (Cloud Native)

O projeto evoluiu de um ambiente local para uma infraestrutura distribuída em nuvem, garantindo escalabilidade e acesso global:

* **Database:** PostgreSQL Serverless hospedado na **Neon.tech**.
* **Backend:** API FastAPI (Python) hospedada no **Render**.
* **Frontend:** SPA React + Vite + Tailwind CSS (v4) hospedada na **Vercel**.
* **Monitoring:** Health checks automatizados via **UptimeRobot** para mitigação de *Cold Start* no Render.

---

## 🛠️ 2. Destaques de Engenharia (The Jala Way)

Durante o desenvolvimento, foram resolvidos desafios críticos de software para garantir a robustez do sistema:

* **Data Integrity (Timezone Fix):** Implementação de lógica de manipulação de datas baseada em strings ISO e processamento via `.split('-')`. Esta abordagem eliminou bugs de fuso horário (GMT) que causavam o deslocamento de datas de vencimento no frontend, garantindo que o dado persistido seja exatamente o exibido.
* **High Availability (Uptime):** Configuração de rotas de monitoramento compatíveis com o método `HEAD` através de `@app.api_route`. Isso permite que serviços externos de monitoramento mantenham a instância do Render ativa 24/7, reduzindo o tempo de resposta inicial de 20s para < 2s.
* **CI/CD Pipeline:** Fluxo automatizado de deploy via GitHub. Gestão de múltiplas identidades de commit e resolução de conflitos de histórico para manter o ambiente de produção sempre sincronizado com o repositório principal.

---

## 📖 3. Status das Funcionalidades

### **Dashboard & Navegação** [✅ CONCLUÍDO]
* Navegação mensal dinâmica com o componente `MonthNavigator`.
* Filtros inteligentes por estado: **Pendentes**, **Pagas** e **Atrasadas**.
* Indicador de contas vencendo no dia atual.

### **Controle de Payables (Contas a Pagar)** [✅ CONCLUÍDO]
* CRUD completo com persistência no Neon PostgreSQL.
* Lógica de "Baixa" (Marcar como Pago) com atualização de status em tempo real.
* Sistema de **Undo** (Desfazer) para exclusões acidentais integrado a notificações *Toast*.

### **Importação de Extratos** [✅ CONCLUÍDO]
* Parser de CSV com mapeamento dinâmico de colunas (Data, Descrição, Valor).
* Feedback visual de progresso e redirecionamento automático.

---

## 📊 4. Modelagem de Dados (Entidade Principal)

### **Payable (Contas a Pagar)**
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `title` | String | Descrição amigável da despesa |
| `due_date` | String (ISO) | Vencimento (YYYY-MM-DD) - **Imune a Timezone** |
| `amount` | Decimal | Valor monetário da conta |
| `status` | Enum | `PENDING`, `PAID` |
| `category_id` | UUID | Relacionamento com a categoria da despesa |

---

## 📅 5. Road Map (Próximos Passos)

1.  **Categorização Inteligente:** Lógica para agrupar gastos automaticamente (ex: "Mercado", "Assinaturas").
2.  **Gráficos de Consumo:** Visualização de gastos por categoria utilizando a biblioteca Recharts.
3.  **PWA Setup:** Configuração de manifest e service workers para instalação como App nativo no iOS/Android.
4.  **Módulo de Milhas:** Registro de retorno financeiro (cashback/milhas) por transação paga.

---
**Última atualização:** 31 de Março de 2026
*Desenvolvido por Dennys Alves como projeto prático de Software Engineering.*