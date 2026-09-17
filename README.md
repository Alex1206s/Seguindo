# Seguindo
Ferramenta para administradores de redes sociais que verificam as saídas e entradas de usurário na barra de seguindo comparando a data base de um arquivo com o novo arquivo 

## Uso

Extrai a lista completa de "seguindo" de um perfil do Instagram a partir de uma URL,
autenticando com uma conta que você administra, e compara automaticamente com a
extração anterior (entradas/saídas).

```bash
pip install -r requirements.txt

# opcional: evita digitar toda vez
export INSTA_LOGIN="sua_conta"

python3 extrair_seguindo.py --url https://www.instagram.com/perfil_alvo/
```

Na primeira execução será pedida a senha (e o código de 2FA, se houver) da conta
usada para logar; a sessão fica salva em `.sessoes/` para as próximas execuções não
precisarem logar de novo (reduz o risco de bloqueio por parte do Instagram).

Cada extração é salva em `dados/<usuario_alvo>/<usuario_alvo>_<timestamp>.json` e o
script já imprime no terminal quem passou a ser seguido e quem deixou de ser seguido
desde a última extração.

**Importante:** o Instagram não expõe a lista de "seguindo" pela API oficial (Graph
API), nem mesmo do próprio dono da conta — por isso o script usa a biblioteca
[Instaloader](https://instaloader.github.io/), autenticando como uma conta que você
administra. Use apenas em contas próprias ou que você tem autorização para gerenciar,
e evite rodar com muita frequência para não esbarrar em limites de requisição do
Instagram.
