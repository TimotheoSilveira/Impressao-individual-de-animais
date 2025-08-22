# Pipeline — Importar, Validar e Gerar PDF (Streamlit)

App para importar planilhas **CSV/XLSX**, normalizar cabeçalhos, executar **validações básicas** e gerar um **PDF** com logotipo, cabeçalho e rodapé.

## ✨ Principais recursos

* Upload de **CSV/XLSX** (detecta separador e encoding via `chardet`).
* Normalização de colunas para `snake_case` com mapeamento das colunas conhecidas.
* **Validações** de faixas plausíveis (ex.: `percent_rank`, `lactation_number`, datas etc.).
* **PDF** em A4 paisagem com **logotipo**, **cabeçalho** (título) e **rodapé** (data/hora, contato, numeração de página).
* Paginação **horizontal por colunas** (configurável) para tabelas largas.

## 📁 Estrutura sugerida do repositório

```
.
├─ app.py                  # este app
├─ requirements.txt        # dependências
└─ README.md               # este arquivo
```

*(Opcional)* adicione `runtime.txt` com a versão do Python (ex.: `python-3.11`).

## 🧰 Requisitos

* Python 3.10+ (recomendado **3.11**)
* Pacotes listados em `requirements.txt`

## ▶️ Rodando localmente

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Acesse a URL local exibida pelo Streamlit.

## ☁️ Publicando no Streamlit Community Cloud

1. Suba estes arquivos para um repositório no **GitHub**.
2. Vá em [https://streamlit.io](https://streamlit.io) → **Community Cloud** → **Deploy an app**.
3. Selecione o repositório/branch e indique `app.py` como **App file**.
4. Confirme o deploy. O app ficará acessível em uma URL pública.

> Dica: Se precisar de versão específica do Python, crie `runtime.txt` com o conteúdo `python-3.11`.

## 🧪 Como usar o app

1. **Upload** da planilha (barra lateral).
2. (Opcional) Upload do **logotipo** (PNG/JPG).
3. Ajuste **Título do relatório**, **Contato (rodapé)** e **Máx. colunas por página (PDF)**.
4. Navegue pelas abas: *Prévia*, *Validação*, *Exportar CSV*, *PDF*.
5. Clique em **📄 Baixar relatório em PDF**.

## 🧩 Notas técnicas

* Importa CSV com auto-detecção de separador (`engine='python'`) e tenta `;`, `,` e `\t` como fallback.
* Colunas "Unnnamed" no Excel são removidas.
* Datas são convertidas com `errors='coerce'` (valores inválidos viram `NaT`).
* A validação gera um dataframe de inconsistências (linha/coluna/valor/motivo) e permite filtro por coluna.
* O PDF usa **ReportLab** (`SimpleDocTemplate` + `LongTable`) e desenha **cabeçalho/rodapé** via canvas.

## 🔧 Solução de problemas

* **Pacote faltando**: confira `requirements.txt` e refaça o deploy/instalação.
* **Logo não aparece no PDF**: verifique se é PNG/JPG válido; o app salva um temporário antes de gerar o PDF.
* **Planilha muito larga/grande**: aumente o *Máx. colunas por página (PDF)*, reduza linhas exportadas (se necessário, adaptar o código para limitar `n` linhas por desempenho).
* **Erro de encoding**: experimente salvar o CSV em UTF-8 (com BOM) ou use Excel/XLSX.

## 🛡️ Privacidade

Todos os dados enviados são processados na sessão do app. Em hospedagens públicas, evite subir dados sensíveis.

---

Se quiser, posso adicionar um `runtime.txt` e um `.gitignore` prontos. Também posso converter a exportação para **Excel (XLSX)** com múltiplas abas (ex.: por `percent_rank`).
