# Testar o sync da Pluggy ao vivo, localmente

Na maioria dos casos você **não precisa disto**: `tests/test_bill_precision.py` e
os testes de `bank_sync_service` rodam contra snapshots gravados
(`scripts/pluggy_capture.py`). Use este runbook só quando precisar exercitar o
que não dá pra fixturar:

- o handshake OAuth de conectar/reconectar um banco (`item/created`);
- a entrega de webhook ponta a ponta;
- comportamento novo do SDK que só um payload real revela.

## Segredo no path da webhook

`POST /webhooks/pluggy` é público (a Pluggy não injeta credenciais). Com
`PLUGGY_WEBHOOK_SECRET` setado, a URL vira `POST /webhooks/pluggy/<secret>` e o
path sem segredo vira no-op — quem descobrir a URL antiga não consegue mais
disparar sync.

**Produção:** gerar um segredo (`python -c "import secrets; print(secrets.token_urlsafe(24))"`),
setar `PLUGGY_WEBHOOK_SECRET` no Render, e atualizar a webhook URL no dashboard
da Pluggy para `https://<backend>/webhooks/pluggy/<secret>`. Fazer nessa ordem:
o path antigo continua respondendo 200 (sem agir) durante a troca, e o
`daily-sync` das 8h cobre o intervalo.

## Opção A — repontar o webhook existente para um túnel (zero setup extra)

1. Túnel para o backend local:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   # ou: ngrok http 8000
   ```
2. No dashboard da Pluggy, trocar a webhook URL para
   `https://<url-do-túnel>/webhooks/pluggy/<PLUGGY_WEBHOOK_SECRET-local>`.
3. Rodar o backend local (`ENVIRONMENT=development`, banco do docker-compose).
4. Testar: conectar um banco pelo app local, ou forçar um update do item no
   dashboard da Pluggy.
5. **Ao terminar: devolver a webhook URL para produção.** Enquanto o webhook
   aponta pro túnel, produção não recebe eventos (o cron diário cobre).

`cloudflared tunnel --url` gera uma URL nova a cada execução → você reconfigura
o webhook toda vez. Para uma URL estável, ver a Opção B.

## Opção B — túnel nomeado + 2ª Development Application

Vale a pena se você testa ao vivo com frequência.

1. **Túnel nomeado** (Cloudflare, o domínio `mandit.com.br` já é seu):
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create lifeos-dev
   cloudflared tunnel route dns lifeos-dev dev-lifeos.mandit.com.br
   # ~/.cloudflared/config.yml aponta dev-lifeos.mandit.com.br → http://localhost:8000
   cloudflared tunnel run lifeos-dev
   ```
2. **2ª Development Application** em dashboard.pluggy.ai → gera
   `PLUGGY_CLIENT_ID`/`SECRET` próprios (a Pluggy só aceita **1 webhook por
   aplicação**, então dev e prod não coexistem na mesma app).
3. Habilitar o conector MeuPluggy nessa 2ª app; registrar a webhook URL
   `https://dev-lifeos.mandit.com.br/webhooks/pluggy/<secret-local>`.
4. No `.env` local, usar as credenciais da 2ª app.
5. Reconectar cada banco pelo app local uma vez (OAuth contra a 2ª app).

Produção segue intocada — é outra aplicação, outro webhook.
