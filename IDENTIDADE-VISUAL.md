# Identidade visual — Observatório EE

**Nome:** Observatório EE  
**Descrição:** repositório digital de teses e dissertações brasileiras em Educação Estatística  
**Recorte:** 1984–2013 · 259 trabalhos · 57 instituições · 14 estados · 5 regiões

A identidade parte de uma premissa simples: **parecer um repositório acadêmico, não um produto
de tecnologia**. Por isso ela é construída sobre a linguagem do tema Tainacan Interface — Roboto,
paleta teal/cinza, ícones TainacanIcons, cantos retos, linhas finas e nenhum gradiente decorativo.

---

## 1. Marca

### Conceito

O símbolo é um **observatório em órbita**: arcos concêntricos formam uma lente/olho, com um
ponto central e dois satélites laranja. A leitura remete a observação, memória e circulação do
conhecimento.

- **Marca principal:** arcos azul-petróleo `#174B57`, miolo branco e acentos laranja `#D96A3A`.
- **Marca inversa:** arcos brancos, miolo azul e acentos laranja, para fundos escuros.
- **Wordmark:** “Observatório EE” em Roboto Bold, com o subtítulo em Roboto Regular.
- **Arquivos:** `assets/brand/logo-observatorio.svg` (horizontal), `mark-observatorio.svg`
  (símbolo) e `mark-observatorio-inverse.svg` (fundo escuro).

### Arquivos

```
site/public/assets/brand/
├── mark.svg                 # marca principal (64 × 64)
├── mark-inverse.svg         # para fundos escuros
├── mark-mono.svg            # monocromática
├── logo-horizontal.svg      # marca + wordmark
├── favicon.svg              # favicon
├── og-image.png             # cartão de compartilhamento 1200 × 630
├── og-image.html            # fonte editável do cartão
└── design-tokens.json       # tokens para Tokens Studio/Figma
```

### Uso

- Área de respiro mínima: **metade da altura da marca** em todos os lados.
- Tamanho mínimo digital: **24 px** para a marca; **120 px** para o logo horizontal.
- Não deformar, não aplicar sombra, não usar gradiente, não trocar as cores fora das versões
  previstas.
- Em fundos fotográficos, usar a versão inversa ou aplicar uma faixa sólida de contraste.

---

## 2. Paleta

A paleta é a do **Observatório EE**: branco, azul-petróleo, azul secundário, cinza azulado e um
laranja pontual. A tipografia sem serifa fica mais discreta e o conjunto assume uma linguagem de
repositório acadêmico.

| Token | Hex | Uso |
|---|---|---|
| `primary` | `#174B57` | marca, títulos, botão principal, rodapé |
| `primary-dark` | `#123B45` | hover e estados mais escuros |
| `secondary` | `#2E7D89` | links, kicker e apoios |
| `accent` | `#D96A3A` | pontos da marca e realces pontuais |
| `ink` | `#1D2F34` | títulos e texto principal |
| `text` | `#4F6266` | corpo de texto e metadados |
| `muted` | `#7B8C90` | legendas, contagens, textos auxiliares |
| `border` | `#D9E3E4` | linhas, divisórias e bordas |
| `surface` | `#FFFFFF` | fundo de cartões e barras |
| `canvas` | `#E8F0F1` | hero e blocos suaves |

O laranja não é cor de texto corrido: aparece nos satélites da marca, no filete do hero da coleção
e em pequenos destaques. As séries de gráficos usam tints de `#174B57` e `#2E7D89`.

**Contraste:** texto principal sobre branco e `text` sobre `canvas` passam em AA. Nunca usar
`muted` para texto essencial em tamanho pequeno; ele é para legendas e contagens.

---

## 3. Tipografia

**Família:** Roboto (400, 500, 700), auto-hospedada em `assets/fonts/roboto/`.

| Papel | Tamanho | Peso | Observação |
|---|---|---|---|
| Display / capa | 56–64 px | 500 | título do cartão de compartilhamento |
| H1 de página | 24 px | 700 | ficha e cabeçalhos de seção |
| Título de item | 24 px | 700 | com linha teal de 2 px abaixo |
| Corpo | 14 px | 400 | entrelinha 1.55–1.7 |
| Metadado (label) | 12–13 px | 500 | caixa alta, `letter-spacing` 0.08–0.12em |
| Auxiliar | 12 px | 400 | contagens, legendas, rodapé |
| Números | 24–36 px | 500 | `font-variant-numeric: tabular-nums` |

Não usar fonte serifada, display decorativa ou mais de três pesos. A hierarquia vem do tamanho,
do peso e do espaço — não de cores berrantes.

---

## 4. Grade, espaço e forma

- Largura máxima de conteúdo: **1400 px**; margens laterais de **4,1667vw**.
- Espaçamentos base: **4, 8, 12, 16, 24, 32, 48, 64, 72 px**.
- Raios: **0–3 px**. Cartões e painéis não são “pílulas”.
- Bordas: **1 px** `#DBDBDB`; títulos de página com **2 px** teal.
- Sombras: apenas a sombra sutil do menu fixo; nada de cartões flutuantes.
- Ícones: **TainacanIcons**, 16–20 px, sempre com `aria-hidden` quando decorativos.
- Imagens: miniaturas tipográficas geradas por trabalho (4:3); capa editorial da coleção em
  `capa-colecao-card.svg`; sem gráficos decorativos, sem colagens, sem emojis.

---

## 5. Componentes

### Cabeçalho

Logo horizontal completo à esquerda; navegação à direita; busca em ícone. Fundo branco, borda
inferior de 1 px e altura de 110 px no desktop. O logo tem 430 px de largura e é a versão
`logo-observatorio.svg`; no mobile, reduz para 265 px.

### Hero da home

Fundo cinza azulado `#E8F0F1`, barra vertical azul, kicker em caixa alta, título em três linhas,
texto de apoio e busca com botão azul. À direita, os números do acervo (259, 57 e 14) separados
por uma linha vertical. O título não usa imagem nem cartão sobreposto.

### Hero da coleção

Faixa `dark` (#174B57) com filete laranja de 3 px, título branco, descrição, estatísticas e botão de
compartilhamento. Não há imagem de capa nem monograma circular sobreposto: o hero é tipográfico e
estável em qualquer largura.

### Capa da coleção

A capa `assets/images/capa-colecao-card.svg` é uma peça editorial 4:3 com a contagem de trabalhos,
o recorte 1984–2013 e a identificação do observatório. É usada no cartão da coleção na home. Não
há série temporal decorativa nem lente; a leitura é feita pelo número e pela tipografia.

### Cartões e tabela

Cada trabalho tem uma miniatura tipográfica 4:3 em `assets/images/thumbs/{id}.svg`, gerada a partir
de tipo, ano, título, autoria e instituição. Os cartões usam grade responsiva de quatro colunas em
desktop, título em Roboto 500 com duas linhas, metadados em duas linhas e resumo justificado em até
três linhas. A tabela usa miniatura de 64 × 48 px. Tags de palavra-chave com borda de 1 px, fundo
branco e texto `text`; nunca uma única tag com várias palavras.

### Rodapé

Fundo `dark`, marca inversa, colunas de links e crédito ao Tainacan. Links em `#9F9F9F`; hover
branco.

---

## 6. Tom de voz

- **Substantivo, não slogan.** “Acervo”, “registro”, “formação”, “pesquisa”, “instituição”.
- **Direto e acadêmico.** Sem exclamações, sem “incrível”, sem linguagem de marketing.
- **Transparente.** Quando um dado não foi localizado, dizer “não localizado” e indicar a fonte.
- **Português do Brasil.** Termos técnicos em minúscula; siglas explicadas na primeira aparição.

Exemplos:

- “Explorar o acervo” (não “Descubra agora!”)
- “Resumo não localizado no repositório; texto a partir dos objetivos da pesquisa.”
- “Voltar para o acervo”

---

## 7. Figma

O MCP remoto do Figma está configurado em `~/.config/opencode/opencode.jsonc` como
`figma` (`https://mcp.figma.com/mcp`). Para usar:

1. rode `/mcps` no OpenCode e autentique a conta Figma;
2. informe o link do arquivo Figma;
3. o agente `figma` lê estilos, componentes e frames antes de propor mudanças.

Sem autenticação/arquivo, o agente trabalha com os SVGs e `design-tokens.json` deste diretório.
Os tokens estão no formato do **Tokens Studio** e podem ser importados diretamente em um arquivo
Figma. Os SVGs são vetoriais e preservam a marca em qualquer escala.

---

## 8. O que evitar

- Gradientes, brilhos, sombras coloridas e cartões com cantos de 16–24 px.
- Ícones genéricos de “IA”, robôs, lâmpadas, engrenagens ou emojis.
- Paleta arco-íris; usar no máximo um acento por gráfico.
- Fotos de banco de imagens com pessoas genéricas ou cenas de escritório.
- Títulos em caixa alta em blocos longos; reservar a caixa alta para labels e kickers.
- Texto pequeno em `muted` sobre `canvas` sem necessidade.
- Links do Sucupira como se fossem links públicos estáveis.
