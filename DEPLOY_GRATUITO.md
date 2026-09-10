# CondoPro Gestão — publicação gratuita

Arquitetura: Streamlit Community Cloud + GitHub + Supabase gratuito.

1. Crie um repositório privado no GitHub e envie esta pasta.
2. Crie um projeto gratuito no Supabase.
3. No Streamlit Community Cloud, crie um app conectado ao repositório.
4. Use `app.py` como arquivo principal.
5. Cadastre as chaves em App settings > Secrets.
6. Nunca envie `secrets.toml`, banco local ou comprovantes ao GitHub.

A versão local continua funcional. Antes do uso simultâneo online por vários usuários,
a camada SQLite deve ser migrada definitivamente para PostgreSQL/Supabase.
