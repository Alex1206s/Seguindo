# Seguindo
Ferramenta para administradores de redes sociais que verificam as saídas e entradas de usurário na barra de seguindo comparando a data base de um arquivo com o novo arquivo 

## Extração de imagens de PDF

Quando a lista de "seguindo" é exportada como PDF (ex.: capturas de tela salvas
página a página), use `extrair_imagens_pdf.py` para extrair cada imagem
embutida e gerar uma listagem estruturada com os metadados (página,
dimensões, tamanho, etc.).

Requer o utilitário `pdfimages` (pacote `poppler-utils`):

```bash
sudo apt install poppler-utils   # Debian/Ubuntu
brew install poppler             # macOS
```

Uso:

```bash
python3 extrair_imagens_pdf.py Base_seguindo_14_09.pdf -o imagens_extraidas --formato json
```

Isso cria, dentro de `imagens_extraidas/`, um PNG para cada imagem
encontrada no PDF e um arquivo `listagem.json` (ou `.csv`, conforme
`--formato`) com os metadados de cada imagem — substituindo a saída bruta de
`pdfimages -list`, que é apenas texto tabular e fica ilegível ao ser copiada
ou processada por outras ferramentas.
