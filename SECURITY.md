# Política de Segurança

LifeOS é um projeto pessoal/portfólio de código aberto (uso real, dados
financeiros reais do dono via Open Finance). Reportes de segurança são
levados a sério mesmo sendo um projeto de um único mantenedor.

## Como reportar uma vulnerabilidade

**Não abra uma issue pública.** Use uma das duas vias privadas:

1. [GitHub Security Advisories](https://github.com/dennys-swe/LifeOS/security/advisories/new) — preferencial, mantém a conversa e o disclosure no próprio repositório.
2. E-mail para o mantenedor (perfil do GitHub [@dennys-swe](https://github.com/dennys-swe)).

Inclua: passos para reproduzir, impacto esperado e, se possível, uma prova de
conceito. Resposta em até 7 dias corridos.

## Escopo

Em escopo:
- Backend (`backend/`): API FastAPI, autenticação, isolamento multi-tenant, integração Pluggy.
- Frontend (`frontend/`): SPA React.
- Infraestrutura descrita no repo (Render, Vercel, Neon) na medida em que a configuração está versionada aqui.

Fora de escopo:
- Vulnerabilidades nas dependências de terceiros em si (reporte direto ao projeto upstream; o Dependabot já monitora as usadas aqui).
- Engenharia social, ataques físicos, DoS.
- A conta pessoal do Pluggy/MeuPluggy usada em desenvolvimento.

## Decisões de segurança já avaliadas

**JWT em `localStorage` em vez de cookie `httpOnly`.** Vulnerável a XSS (um
script malicioso injetado no frontend pode ler o token). Mantido por
simplicidade — o frontend é uma SPA separada do backend (domínios diferentes:
Vercel + Render), e cookie `httpOnly` cross-site exigiria `SameSite=None` +
`Secure` e ainda outra camada de proteção contra CSRF, trocando um risco por
outro sem eliminar a superfície. Mitigação real é não introduzir XSS no
frontend (sem `dangerouslySetInnerHTML`/`innerHTML` com dado não sanitizado).
Reavaliar se o frontend um dia carregar conteúdo de terceiros.

**CORS**: `allow_origins` restrito a `CORS_ORIGINS` (nunca `*` com
credentials); métodos e headers limitados aos que o frontend usa de fato.

**Erros de sync não vazam detalhe interno**: `last_sync_error` (exposto via
`GET /bank-accounts`) guarda só o nome da exceção — o detalhe completo (que
pode incluir corpo de resposta da Pluggy) vai para o log/Sentry, nunca para a
API.

**Headers de segurança** aplicados em toda resposta: HSTS,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: strict-origin-when-cross-origin` e uma CSP básica
(`default-src 'none'`) fora de `/docs`/`/redoc`.

## Segredos

`.env` nunca é commitado (`.gitignore`); `.env.example` só tem placeholders.
Secret scanning + push protection estão habilitados no repositório.
