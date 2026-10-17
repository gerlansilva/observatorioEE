# Observatório EE

Repositório digital de teses e dissertações brasileiras em **Educação Estatística** (1984–2013), com interface inspirada no tema **Tainacan Interface**.

O site é uma publicação estática: os dados são extraídos da planilha de estado da arte, enriquecidos com informações da CAPES, da BDTD e dos repositórios institucionais, e publicados como arquivos JSON e SVG. Não há banco de dados nem servidor de aplicação em produção.

- **Repositório:** <https://github.com/gerlansilva/observatorioEE>
- **Publicação:** Cloudflare Pages, a partir da pasta `site/public`
- **Recorte:** 259 trabalhos, 1984–2013

## Sumário

- [O que é o projeto](#o-que-é-o-projeto)
- [Números atuais](#números-atuais)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Rodando localmente](#rodando-localmente)
- [Pipeline de dados](#pipeline-de-dados)
- [Publicação no Cloudflare Pages](#publicação-no-cloudflare-pages)
- [Painel administrativo](#painel-administrativo)
- [Atualizando o acervo](#atualizando-o-acervo)
- [Critérios e limitações](#critérios-e-limitações)
- [Identidade visual](#identidade-visual)
- [Créditos](#créditos)
- [Licença e uso](#licença-e-uso)

## O que é o projeto

O Observatório EE reúne, organiza e disponibiliza informações sobre a produção brasileira de teses e dissertações em Educação Estatística. O ponto de partida é o levantamento de estado da arte realizado por Rodrigo Medeiros dos Santos durante seu doutorado na UNICAMP, posteriormente validado pela equipe do projeto.

Cada registro contém, quando localizado:

- título, autoria, orientação, ano, tipo e grau;
- instituição, programa, cidade, estado e região;
- área, nível de ensino, foco temático e conteúdo enfocado;
- resumo em português;
- palavras-chave em português;
- link do registro na BDTD;
- link do repositório institucional ou do texto completo;
- miniatura editorial própria.

O site **não hospeda os arquivos das teses e dissertações**. Os links levam ao repositório de origem, e a disponibilidade do arquivo depende da instituição que o publica.

## Números atuais

| Indicador | Total |
|---|---:|
| Trabalhos catalogados | 259 |
| Dissertações | 221 |
| Teses | 38 |
| Instituições | 57 |
| Estados | 14 |
| Regiões | 5 |
| Registros com link BDTD | 172 |
| Registros com link de repositório | 182 |
| Resumos em português | 189 |
| Registros com palavras-chave em português | 190 |
| Miniaturas editoriais | 259 |

Os números do site são gerados a partir de `site/public/data/agregados.json`; não são valores fixos no HTML.

## Funcionalidades

- Busca por título, autoria, instituição, programa, assunto e palavras-chave.
- Filtros por ano, grau, tipo, região, estado, instituição, área, foco temático, conteúdo e nível de ensino.
- Visualização em tabela ou cartões.
- Paginação e ordenação.
- Painel de filtros recolhível.
- Página de item com metadados, resumo e palavras-chave em português.
- Panorama com produção por ano, grau, conteúdo, foco e instituições.
- Mapa interativo do Brasil com totais por estado e por região.
- Download dos dados em CSV e JSON.
- Miniaturas tipográficas determinísticas para todos os registros.
- Layout responsivo e navegação por teclado.
- Painel administrativo em `/admin/` para editar, incluir e excluir fichas, com commits automáticos no GitHub.

## Arquitetura

O projeto é dividido em duas partes:

1. **Pipeline de dados em Python** — lê a planilha original, enriquece os registros e gera os arquivos estáticos.
2. **Front-end estático** — HTML, CSS e JavaScript sem framework, consumindo os JSONs gerados.

```text
planilha (.xls)
      │
      ▼
scripts/extrair.py
      │
      ├──► site/public/data/itens/*.json
      ├──► site/public/data/indice.json
      ├──► site/public/data/agregados.json
      ├──► dados/teses.csv
      └──► dados/qualidade.json
      │
      ▼
enriquecimento CAPES / BDTD / repositórios
      │
      ▼
miniaturas, mapa, índice e validação
      │
      ▼
Cloudflare Pages (site/public)
```

O front-end usa roteamento por hash (`#/acervo`, `#/item/...`, `#/panorama`, `#/sobre`). Isso permite publicar em qualquer host estático sem regras de servidor.

## Estrutura do repositório

```text
observatorioEE/
├── dados/
│   ├── planilha-do-estado-da-arte.xls   # fonte original
│   ├── teses.csv                        # dados normalizados
│   ├── qualidade.json                   # relatório de completude
│   ├── cobertura_bdtd.json              # cobertura por registro
│   ├── malha_uf.json                    # malha IBGE usada no mapa
│   ├── estados_ibge.json                # código IBGE → UF
│   └── agentes/                         # resultados de pesquisa dos agentes
├── scripts/
│   ├── extrair.py                       # planilha → JSON/CSV
│   ├── enriquecer_capes.py              # nomes, orientação e grau (CAPES)
│   ├── enriquecer_bdtd_api.py           # links pela API da BDTD
│   ├── enriquecer_bdtd_registros.py     # resumo, palavras-chave e acesso (BDTD)
│   ├── enriquecer_bdtd_jina.py          # fallback da BDTD via Jina Reader
│   ├── resolver_bdtd_html.py            # resolução de IDs pela busca HTML
│   ├── resolver_bdtd_jina_api.py        # resolução de IDs pela API via Jina
│   ├── extrair_resumos_repositorios.py  # resumos nos repositórios
│   ├── extrair_resumos_portugues.py     # prioriza resumo em português
│   ├── extrair_spelling_bdtd.py         # resumo no campo spelling da BDTD
│   ├── limpar_resumos_metadados.py      # remove metadados do fim dos resumos
│   ├── normalizar_palavras_chave.py     # remove tags em inglês
│   ├── normalizar_resumos_tags.py       # normaliza resumos, tags e links
│   ├── normalizar_nomes.py              # nomes em ordem natural
│   ├── gerar_miniaturas.py              # miniaturas SVG por trabalho
│   ├── gerar_mapa_brasil.py             # malha simplificada dos estados
│   ├── reindexar.py                     # reconstrói índice e agregados
│   ├── relatorio_cobertura.py           # relatório de cobertura
│   ├── exportar_csv.py                  # CSV público
│   ├── aplicar_agentes.py               # aplica resultados históricos
│   ├── aplicar_agentes_pt.py            # aplica resumos/tags dos agentes
│   ├── aplicar_agentes_links.py         # aplica links dos agentes
│   ├── validar.mjs                      # validação de integridade
│   └── enriquecer_bdtd.py               # script legado
├── site/public/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── admin/                           # painel administrativo
│   │   ├── index.html
│   │   ├── admin.css
│   │   └── admin.js
│   ├── _headers                         # cabeçalhos do Cloudflare Pages
│   ├── assets/
│   │   ├── brand/                       # marca, logo, favicon, OG e tokens
│   │   ├── fonts/                       # Roboto e TainacanIcons
│   │   ├── images/
│   │   │   ├── thumbs/                  # 259 miniaturas SVG
│   │   │   └── capa-colecao-card.svg
│   │   └── vendor/                      # Bootstrap e Tainacan Interface
│   ├── data/
│   │   ├── indice.json
│   │   ├── agregados.json
│   │   ├── mapa-brasil.json
│   │   └── itens/                       # 259 fichas completas
│   └── dados/teses.csv
├── functions/api/admin/                 # API do painel no Cloudflare Pages
│   ├── _utils.js
│   ├── session.js
│   └── item.js
├── .github/workflows/
│   ├── deploy.yml
│   └── reindex.yml
├── requirements.txt
├── package.json
└── README.md
```

## Rodando localmente

Requisitos:

- Python 3.11+
- Node.js 20+ (apenas para validação e publicação)

```bash
git clone https://github.com/gerlansilva/observatorioEE.git
cd observatorioEE

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# servir o site
python3 -m http.server 8082 --directory site/public
```

Abra <http://localhost:8082>.

Para validar os dados:

```bash
node scripts/validar.mjs
```

O `package.json` também oferece:

```bash
npm run serve
npm run validar
```

## Pipeline de dados

Os comandos abaixo assumem o ambiente virtual ativo.

### 1. Extrair a planilha

```bash
python scripts/extrair.py
```

Gera as fichas em `site/public/data/itens/`, o índice, os agregados, o CSV e o relatório de qualidade.

### 2. Enriquecer com a CAPES

```bash
python scripts/enriquecer_capes.py
```

Completa nome do autor, orientação, grau, instituição e programa. O script é retomável e usa cache em `.cache/capes`.

### 3. Enriquecer com a BDTD

```bash
python scripts/enriquecer_bdtd_api.py --no-bdtd-only --force
python scripts/enriquecer_bdtd_registros.py
```

O primeiro comando busca registros e links; o segundo lê a página do registro e extrai resumo, palavras-chave em português e link de acesso.

Quando o host da BDTD recusa conexões, os fallbacks são:

```bash
python scripts/enriquecer_bdtd_jina.py --resolve-missing
python scripts/resolver_bdtd_jina_api.py
python scripts/extrair_spelling_bdtd.py --force
```

### 4. Completar resumos e palavras-chave

```bash
python scripts/extrair_resumos_portugues.py
python scripts/extrair_spelling_bdtd.py
python scripts/limpar_resumos_metadados.py
python scripts/normalizar_palavras_chave.py
python scripts/normalizar_resumos_tags.py
```

### 5. Gerar miniaturas e mapa

```bash
python scripts/gerar_miniaturas.py
python scripts/gerar_mapa_brasil.py
```

O mapa só precisa ser regenerado quando a malha do IBGE for atualizada. Os totais por estado e região são recalculados no `reindexar.py`.

### 6. Reindexar, exportar e validar

```bash
python scripts/reindexar.py
python scripts/exportar_csv.py
python scripts/relatorio_cobertura.py
node scripts/validar.mjs
```

> Os scripts de agentes são opcionais e servem para completar lacunas de resumos, palavras-chave e links. Eles não são necessários para servir o site.

## Publicação no Cloudflare Pages

A pasta publicada é **`site/public`**. O site não exige etapa de build.

### Opção A — integração direta com o GitHub

1. No painel do Cloudflare, acesse **Workers & Pages → Create → Pages → Connect to Git**.
2. Selecione o repositório `gerlansilva/observatorioEE`.
3. Configure:
   - **Framework preset:** None
   - **Build command:** deixe vazio
   - **Build output directory:** `site/public`
   - **Production branch:** `main`
4. Publique.
5. Em **Custom domains**, adicione o domínio desejado.

### Opção B — GitHub Actions

O repositório já inclui `.github/workflows/deploy.yml`. Configure em **Settings → Secrets and variables → Actions**:

| Tipo | Nome | Conteúdo |
|---|---|---|
| Secret | `CLOUDFLARE_API_TOKEN` | token com permissão **Cloudflare Pages: Edit** |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | ID da conta Cloudflare |
| Variable | `CLOUDFLARE_PROJECT` | nome do projeto no Cloudflare Pages (opcional) |

O workflow executa `node scripts/validar.mjs` e publica `site/public` com Wrangler. Enquanto os secrets não estiverem configurados, a etapa de publicação é ignorada e o workflow continua apenas com a validação.

### Cabeçalhos

O arquivo `site/public/_headers` define cabeçalhos de segurança e políticas de cache para o Cloudflare Pages.

## Painel administrativo

O painel fica em **`/admin/`** e permite:

- editar fichas existentes;
- incluir novos trabalhos;
- excluir trabalhos;
- gerenciar resumo, palavras-chave e links.

O painel não usa banco de dados: cada operação cria um commit no GitHub. O workflow
`.github/workflows/reindex.yml` detecta a alteração, reconstrói `indice.json`, `agregados.json`,
as miniaturas e o CSV, e faz um novo commit. Em seguida, o Cloudflare Pages republica o site.

### Configuração no Cloudflare Pages

Em **Settings → Environment variables**, configure para Production e Preview:

| Variável | Uso |
|---|---|
| `ADMIN_TOKEN` | senha/token de acesso ao painel; use uma string longa e aleatória |
| `GITHUB_TOKEN` | fine-grained PAT com permissão **Contents: Read and write** neste repositório |
| `GITHUB_REPO` | opcional; padrão `gerlansilva/observatorioEE` |
| `GITHUB_BRANCH` | opcional; padrão `main` |

O `GITHUB_TOKEN` fica apenas no servidor do Cloudflare Pages Functions e nunca é enviado ao
navegador. O `ADMIN_TOKEN` é solicitado na tela de login e fica somente na sessão do navegador.

Depois de cadastrar as variáveis, faça um novo deploy para que as Functions as recebam.

### Segurança recomendada

Além do token do painel, proteja as rotas `/admin/*` e `/api/admin/*` com **Cloudflare Access**
(Zero Trust), permitindo apenas o seu e-mail. O token administrativo continua sendo necessário
como segunda camada.

### Como usar

1. Acesse `https://SEU-DOMINIO/admin/`.
2. Informe o `ADMIN_TOKEN`.
3. Selecione uma ficha na lista ou clique em **Novo**.
4. Edite os campos e clique em **Salvar alterações**.
5. O commit é criado e a reindexação automática é iniciada no GitHub.
6. Aguarde o workflow e a publicação do Cloudflare Pages.

Para editar localmente as Functions, use o Wrangler:

```bash
npx wrangler pages dev site/public
```

Defina `ADMIN_TOKEN`, `GITHUB_TOKEN`, `GITHUB_REPO` e `GITHUB_BRANCH` no ambiente local.

## Atualizando o acervo

O caminho mais simples é usar o painel em `/admin/`. Para edições em lote ou reconstrução completa:

1. Atualize a planilha original ou os arquivos de dados.
2. Rode o pipeline de extração e enriquecimento.
3. Rode `python scripts/reindexar.py`.
4. Rode `python scripts/gerar_miniaturas.py` para gerar as novas capas.
5. Valide com `node scripts/validar.mjs`.
6. Faça commit e push; o Cloudflare Pages republica o site.

Os gráficos do panorama, o mapa e os totais da home são recalculados a partir de `agregados.json`, portanto acompanham automaticamente os novos registros depois da reindexação.

## Critérios e limitações

- O recorte temporal é o da planilha original: **1984–2013**.
- Nem todos os trabalhos estão depositados na BDTD. Quando não há registro BDTD, o link do repositório institucional é usado como alternativa.
- Alguns repositórios bloqueiam acesso automatizado, estão fora do ar ou não oferecem resumo público. Nesses casos, a ficha usa o campo “Problema e Objetivos” da planilha como texto de apoio, com nota explícita.
- Resumos e palavras-chave foram mantidos em português. Não há tradução automática de abstracts.
- A classificação de área, foco temático e nível de ensino segue a planilha e as normalizações documentadas no código.
- O site não hospeda PDFs nem substitui a conferência na fonte original.

## Identidade visual

A identidade e a paleta estão documentadas em [`IDENTIDADE-VISUAL.md`](./IDENTIDADE-VISUAL.md) e nos arquivos de `site/public/assets/brand/`.

- Azul institucional: `#174B57`
- Azul secundário: `#2E7D89`
- Cinza azulado: `#E8F0F1`
- Branco: `#FFFFFF`
- Laranja de destaque: `#D96A3A`
- Tipografia: Roboto
- Ícones: TainacanIcons
- Tokens: `site/public/assets/brand/design-tokens.json`

As miniaturas dos trabalhos são geradas por `scripts/gerar_miniaturas.py`. O mapa usa a malha oficial do IBGE, simplificada por `scripts/gerar_mapa_brasil.py`.

## Créditos

O acervo foi construído a partir do levantamento de estado da arte realizado pelo **Dr. Rodrigo Medeiros dos Santos** durante seu doutorado na Universidade Estadual de Campinas (UNICAMP), sob a orientação de **Dario Fiorentini**.

- ORCID: <https://orcid.org/0000-0002-9108-9826>
- ORCID: <https://orcid.org/0000-0001-5536-0781>
- Tese: <https://repositorio.unicamp.br/acervo/detalhe/963478>

As informações foram posteriormente validadas por meio de consulta ao **Catálogo de Teses e Dissertações da CAPES** e à **Biblioteca Digital Brasileira de Teses e Dissertações (BDTD)**.

O desenvolvimento deste site é uma iniciativa independente de **Gerlan Silva da Silva**, doutorando do Programa de Pós-Graduação em Educação da Universidade Federal de São Carlos (UFSCar).

## Licença e uso

O código e a documentação deste repositório estão disponíveis para consulta e reuso. Os metadados foram organizados pela equipe do projeto; os textos completos, resumos e imagens de capa pertencem aos autores e às instituições de origem. Ao reutilizar os dados, cite a planilha de origem, a BDTD/CAPES e este repositório.

Sugestão de citação:

> OBSERVATÓRIO EE. *Teses e dissertações em Educação Estatística (1984–2013)*. Repositório digital. Disponível em: <https://github.com/gerlansilva/observatorioEE>. Acesso em: [data].
