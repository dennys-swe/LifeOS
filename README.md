# 💰 Controle Financeiro Pessoal (LifeOS - MVP)

Sistema Fullstack responsivo para gestão financeira. Centraliza a visualização de saldos via importação de extratos e gerencia contas a pagar, com foco total em experiência mobile-first (acesso via iPhone).

---

## 🏗️ 1. Arquitetura do Ecossistema
O projeto opera em um ambiente distribuído para simular um cenário real de produção:
* **Banco de Dados (Persistence):** PostgreSQL rodando em servidor Linux (Notebook Ubuntu).
* **Backend (API):** FastAPI rodando em Windows, servindo como ponte de lógica.
* **Frontend (Interface):** React + Vite + Tailwind CSS (v4) rodando em Windows e acessado via mobile.
* **Client (Mobile):** Safari no iPhone acessando via rede local (IP fixo).

---

## 🛠️ 2. Guia de Setup (Desenvolvimento)

### **Backend (PC Windows)**
1.  **Variáveis de Ambiente (.env):**
    ```text
    DATABASE_URL=postgresql+psycopg2://postgres:jala@192.168.0.6:5432/finance_db
    ```
2.  **Execução para Acesso na Rede:**
    ```powershell
    uvicorn app.main:app --reload --host 0.0.0.0
    ```

### **Frontend (PC Windows)**
1.  **Dependências:** Node.js v24.14+ | npm v11.11+
2.  **Configuração da API (`src/services/api.js`):**
    ```javascript
    const api = axios.create({ baseURL: "[http://192.168.0.8:8000](http://192.168.0.8:8000)" });
    ```
3.  **Execução para Acesso Mobile:**
    ```powershell
    npm run dev -- --host
    ```

---

## 📖 3. Status das Funcionalidades (MVP)

### **Dashboard Financeiro** [✅ CONCLUÍDO]
* Cards de resumo: Saldo Total e Contas a Pagar Pendentes.
* Lista das 5 últimas transações importadas.
* Design Dark Mode responsivo.

### **Importação de Extratos (CSV)** [✅ CONCLUÍDO]
* Página dedicada de Upload com feedback visual.
* Parser automático para colunas de Data, Descrição e Valor.
* Redirecionamento automático pós-importação.

### **Controle de Contas a Pagar (Payables)** [🛠️ EM PROGRESSO]
* API: CRUD funcional via endpoints.
* UI: Visualização básica no dashboard.
* **Próximo Passo:** Criar tela de gerenciamento (Dar baixa em contas pelo celular).

---

## 📊 4. Modelagem de Dados (Entidades)

### **Transaction (Extrato)**
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `date` | Date | Data da operação |
| `description` | String | Nome da transação |
| `amount` | Numeric | Valor (Positivo para entrada, Negativo para saída) |
| `source` | String | Nome do arquivo/banco de origem |

### **Payable (Contas a Pagar)**
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `title` | String | Descrição da conta |
| `due_date` | Date | Vencimento |
| `status` | Enum | PENDING, PAID, OVERDUE |

---

## 📅 5. Road Map (Próximos Passos)
1.  **Gestão de Payables na UI:** Criar lista completa de contas a pagar com botão de "Marcar como Pago".
2.  **Categorização Inteligente:** Lógica para agrupar gastos (ex: "Supermercado", "Lazer").
3.  **Módulo de Milhas/Cashback:** Adicionar campo para registrar retorno financeiro por transação.
4.  **PWA Setup:** Adicionar manifest e ícones para instalação "nativa" no iOS.

---
**Última atualização:** 29/03/2026 - *Ambiente mobile validado no IP 192.168.0.8*


