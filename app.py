import streamlit as st
import pandas as pd
from datetime import timedelta
import plotly.express as px

st.set_page_config(layout="wide", page_title="Análise de campanha de cobrança")

st.title("📊 Análise de eficiência de campanha de cobrança via Whatsapp")
st.markdown("Faça o upload dos seus arquivos para analisar a performance da campanha de notificações.")

# --- Funções de Processamento ---

@st.cache_data
def load_and_process_envios(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file)
        required_cols = ['To', 'Send At']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Arquivo de Envios: Colunas esperadas '{required_cols[0]}' e '{required_cols[1]}' não encontradas.")
            return None

        df_envios = df[['To', 'Send At']].copy()
        df_envios.rename(columns={'To': 'TELEFONE_ENVIO', 'Send At': 'DATA_ENVIO'}, inplace=True)

        df_envios['TELEFONE_ENVIO'] = df_envios['TELEFONE_ENVIO'].astype(str).str.replace(r'^55', '', regex=True).str.replace(r'\.0$', '', regex=True)
        df_envios['TELEFONE_ENVIO'] = df_envios['TELEFONE_ENVIO'].str.strip()

        df_envios['DATA_ENVIO'] = pd.to_datetime(df_envios['DATA_ENVIO'], errors='coerce', dayfirst=True)
        df_envios.dropna(subset=['DATA_ENVIO'], inplace=True)

        st.sidebar.success("Arquivo de Envios processado com sucesso!")
        return df_envios
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Envios: {e}")
        return None

@st.cache_data
def load_and_process_pagamentos(uploaded_file):
    try:
        df = None
        if uploaded_file.name.endswith('.csv'):
            for encoding in ['latin1', 'utf-8', 'cp1252']:
                try:
                    df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding=encoding, header=None)
                    uploaded_file.seek(0)
                    break
                except Exception:
                    uploaded_file.seek(0)
                    continue
            if df is None:
                raise ValueError("Não foi possível ler o arquivo CSV com as codificações tentadas.")
        elif uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file, header=None)
        else:
            raise ValueError("Formato de arquivo de pagamentos não suportado.")

        if df is None or df.empty:
            st.sidebar.error("Arquivo de Pagamentos está vazio ou não pôde ser lido.")
            return None

        if df.shape[1] < 10:
            st.sidebar.error(f"Arquivo de Pagamentos: Esperava pelo menos 10 colunas, mas encontrou {df.shape[1]}.")
            return None

        # --- COLUNAS ESSENCIAIS ---
        col_indices = [0, 5, 8]
        col_names   = ['MATRICULA_PAGAMENTO', 'DATA_PAGAMENTO', 'VALOR_PAGO']

        if df.shape[1] > 12:
            col_indices.append(12)
            col_names.append('TIPO_PAGAMENTO')

        df_pagamentos = df.iloc[:, col_indices].copy()
        df_pagamentos.columns = col_names

        # --- COLUNAS OPCIONAIS (adicionadas ANTES dos dropna, enquanto os tamanhos ainda batem) ---
        IDX_VENCIMENTO  = 4   # <-- confirme
        IDX_TIPO_FATURA = 11  # <-- confirme
        IDX_UTILIZACAO  = 9  # <-- confirme

        if df.shape[1] > IDX_VENCIMENTO:
            df_pagamentos['VENCIMENTO'] = df.iloc[:, IDX_VENCIMENTO].values

        if df.shape[1] > IDX_TIPO_FATURA:
            df_pagamentos['TIPO_FATURA'] = df.iloc[:, IDX_TIPO_FATURA].values

        if df.shape[1] > IDX_UTILIZACAO:
            df_pagamentos['UTILIZACAO'] = df.iloc[:, IDX_UTILIZACAO].values

        # --- TRATAMENTOS (aplicados após todas as colunas estarem no dataframe) ---
        df_pagamentos['MATRICULA_PAGAMENTO'] = df_pagamentos['MATRICULA_PAGAMENTO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        df_pagamentos['DATA_PAGAMENTO'] = pd.to_datetime(df_pagamentos['DATA_PAGAMENTO'], errors='coerce', dayfirst=True)
        df_pagamentos.dropna(subset=['DATA_PAGAMENTO'], inplace=True)

        def parse_valor(val):
            s = str(val).strip()
            if ',' in s:
                # Formato brasileiro: remove separador de milhar (.) e converte decimal (,) para (.)
                s = s.replace('.', '').replace(',', '.')
            return s

        df_pagamentos['VALOR_PAGO'] = df_pagamentos['VALOR_PAGO'].apply(parse_valor)
        df_pagamentos['VALOR_PAGO'] = pd.to_numeric(df_pagamentos['VALOR_PAGO'], errors='coerce')
        df_pagamentos.dropna(subset=['VALOR_PAGO'], inplace=True)

        if 'TIPO_PAGAMENTO' in df_pagamentos.columns:
            df_pagamentos['TIPO_PAGAMENTO'] = df_pagamentos['TIPO_PAGAMENTO'].astype(str).str.strip()
            df_pagamentos['TIPO_PAGAMENTO'] = df_pagamentos['TIPO_PAGAMENTO'].replace('nan', 'Não informado')

        if 'VENCIMENTO' in df_pagamentos.columns:
            df_pagamentos['VENCIMENTO'] = pd.to_datetime(df_pagamentos['VENCIMENTO'], errors='coerce', dayfirst=True)
            df_pagamentos['MES_FATURA']     = df_pagamentos['VENCIMENTO'].dt.month
            df_pagamentos['ANO_FATURA']     = df_pagamentos['VENCIMENTO'].dt.year
            df_pagamentos['MES_ANO_FATURA'] = df_pagamentos['VENCIMENTO'].dt.strftime('%m/%Y')

        if 'TIPO_FATURA' in df_pagamentos.columns:
            df_pagamentos['TIPO_FATURA'] = df_pagamentos['TIPO_FATURA'].astype(str).str.strip()
            df_pagamentos['TIPO_FATURA'] = df_pagamentos['TIPO_FATURA'].replace('nan', 'Não informado')

        if 'UTILIZACAO' in df_pagamentos.columns:
            df_pagamentos['UTILIZACAO'] = df_pagamentos['UTILIZACAO'].astype(str).str.strip()
            df_pagamentos['UTILIZACAO'] = df_pagamentos['UTILIZACAO'].replace('nan', 'Não informado')

        st.sidebar.success("Arquivo de Pagamentos processado com sucesso!")
        return df_pagamentos
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Pagamentos: {e}")
        return None

@st.cache_data
def load_and_process_clientes(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file)

        required_cols = ['TELEFONE', 'MATRICULA', 'SITUACAO']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Arquivo de Clientes: Colunas esperadas não encontradas. Necessário: {required_cols}")
            return None

        colunas_ler = ['TELEFONE', 'MATRICULA', 'SITUACAO']
        for col_opcional in ['CIDADE', 'DIRETORIA']:
            if col_opcional in df.columns:
                colunas_ler.append(col_opcional)

        df_clientes = df[colunas_ler].copy()
        df_clientes.rename(columns={
            'TELEFONE': 'TELEFONE_CLIENTE',
            'MATRICULA': 'MATRICULA_CLIENTE'
        }, inplace=True)

        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].astype(str).str.replace(r'^55', '', regex=True).str.replace(r'\.0$', '', regex=True)
        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].str.strip()

        df_clientes['MATRICULA_CLIENTE'] = df_clientes['MATRICULA_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        df_clientes['SITUACAO'] = pd.to_numeric(df_clientes['SITUACAO'], errors='coerce').fillna(0)

        if 'CIDADE' in df_clientes.columns:
            df_clientes['CIDADE'] = df_clientes['CIDADE'].astype(str).str.strip()
        if 'DIRETORIA' in df_clientes.columns:
            df_clientes['DIRETORIA'] = df_clientes['DIRETORIA'].astype(str).str.strip()

        df_clientes.drop_duplicates(subset=['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE'], inplace=True)

        st.sidebar.success("Arquivo de Clientes processado com sucesso!")
        return df_clientes
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Clientes: {e}")
        return None

# --- Interface Streamlit ---

st.sidebar.header("Upload de Arquivos")
uploaded_envios     = st.sidebar.file_uploader("1. Base de Envios (Notificações - .xlsx)", type=["xlsx"])
uploaded_pagamentos = st.sidebar.file_uploader("2. Base de Pagamentos (.csv ou .xlsx)", type=["csv", "xlsx"])
uploaded_clientes   = st.sidebar.file_uploader("3. Base de Identificação de Clientes (.xlsx)", type=["xlsx"])

st.sidebar.header("Configurações da Análise")
janela_dias = st.sidebar.slider("Janela de dias para considerar o pagamento após o envio da notificação:", 0, 30, 7)

executar_analise = st.sidebar.button("Executar Análise")

df_envios     = None
df_pagamentos = None
df_clientes   = None

if uploaded_envios:
    df_envios = load_and_process_envios(uploaded_envios)
if uploaded_pagamentos:
    df_pagamentos = load_and_process_pagamentos(uploaded_pagamentos)
if uploaded_clientes:
    df_clientes = load_and_process_clientes(uploaded_clientes)

if st.sidebar.checkbox("Mostrar pré-visualização dos dados processados"):
    if df_envios is not None:
        st.subheader("Pré-visualização da Base de Envios")
        st.dataframe(df_envios.head())
    if df_pagamentos is not None:
        st.subheader("Pré-visualização da Base de Pagamentos")
        st.dataframe(df_pagamentos.head())
    if df_clientes is not None:
        st.subheader("Pré-visualização da Base de Clientes")
        st.dataframe(df_clientes.head())

if executar_analise:
    if df_envios is not None and df_pagamentos is not None and df_clientes is not None:

        # Total de clientes notificados
        total_clientes_notificados = df_envios['TELEFONE_ENVIO'].nunique()

        # Total da dívida dos notificados
        df_telefones_unicos_envios = df_envios[['TELEFONE_ENVIO']].drop_duplicates()
        df_lookup_divida = pd.merge(
            df_telefones_unicos_envios,
            df_clientes[['TELEFONE_CLIENTE', 'SITUACAO']],
            left_on='TELEFONE_ENVIO',
            right_on='TELEFONE_CLIENTE',
            how='left'
        )
        total_divida_notificados = df_lookup_divida['SITUACAO'].sum()

        # 1. Cruzar Envios com Clientes
        df_campanha = pd.merge(
            df_envios,
            df_clientes,
            left_on='TELEFONE_ENVIO',
            right_on='TELEFONE_CLIENTE',
            how='left'
        )

        df_campanha.dropna(subset=['MATRICULA_CLIENTE'], inplace=True)
        df_campanha.rename(columns={'MATRICULA_CLIENTE': 'MATRICULA'}, inplace=True)
        df_campanha.drop(columns=['TELEFONE_CLIENTE'], inplace=True)

        df_campanha_unique_notifications = df_campanha.drop_duplicates(subset=['MATRICULA', 'DATA_ENVIO'])

        if not df_campanha_unique_notifications.empty:

            # 2. Cruzar com Pagamentos
            df_resultados = pd.merge(
                df_campanha_unique_notifications,
                df_pagamentos,
                left_on='MATRICULA',
                right_on='MATRICULA_PAGAMENTO',
                how='left'
            )

            # Filtrar pagamentos dentro da janela
            df_pagamentos_campanha = df_resultados[
                (df_resultados['DATA_PAGAMENTO'] > df_resultados['DATA_ENVIO']) &
                (df_resultados['DATA_PAGAMENTO'] <= df_resultados['DATA_ENVIO'] + timedelta(days=janela_dias))
            ].copy()

            # Calcular DIAS_APOS_ENVIO antes das abas
            if not df_pagamentos_campanha.empty:
                df_pagamentos_campanha['DIAS_APOS_ENVIO'] = (
                    df_pagamentos_campanha['DATA_PAGAMENTO'] - df_pagamentos_campanha['DATA_ENVIO']
                ).dt.days

            # Métricas — lógica idêntica à versão que funcionava
            clientes_que_pagaram_matriculas = df_pagamentos_campanha['MATRICULA'].nunique()
            valor_total_arrecadado   = df_pagamentos_campanha['VALOR_PAGO'].sum() if not df_pagamentos_campanha.empty else 0
            taxa_eficiencia_clientes = (clientes_que_pagaram_matriculas / total_clientes_notificados * 100) if total_clientes_notificados > 0 else 0
            taxa_eficiencia_valor    = (valor_total_arrecadado / total_divida_notificados * 100) if total_divida_notificados > 0 else 0
            ticket_medio             = (valor_total_arrecadado / clientes_que_pagaram_matriculas) if clientes_que_pagaram_matriculas > 0 else 0
            custo_campanha           = total_clientes_notificados * 0.05
            roi                      = ((valor_total_arrecadado - custo_campanha) / custo_campanha *100) if custo_campanha > 0 else 0

            # ── ABAS ──────────────────────────────────────────
            aba1, aba2, aba3, aba4, aba5 = st.tabs([
                "📊 Visão Geral",
                "🏙️ Cidade e Diretoria",
                "📅 Análise das Faturas",
                "💳 Canal de Pagamento",
                "📋 Detalhes"
            ])

            # ══════════════════════════════════════════════════
            # ABA 1 — VISÃO GERAL
            # ══════════════════════════════════════════════════
            with aba1:
                st.subheader("Resultados da Análise da Campanha")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total de clientes notificados", f"{total_clientes_notificados}")
                with col2:
                    st.metric("Clientes que pagaram na janela", f"{clientes_que_pagaram_matriculas}")
                with col3:
                    st.metric("Taxa de eficiência (clientes)", f"{taxa_eficiencia_clientes:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))
                    

                col4, col5, col6 = st.columns(3)
                with col4:
                    st.metric("Valor total arrecadado na campanha", f"R$ {valor_total_arrecadado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                with col5:
                    st.metric("Total da dívida dos notificados", f"R$ {total_divida_notificados:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                with col6:
                    st.metric("Taxa de eficiência (valor)", f"{taxa_eficiencia_valor:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

                col7, col8, col9 = st.columns(3)
                with col7:
                    st.metric("Ticket médio", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                with col8:
                    st.metric("Custo da campanha", f"R$ {custo_campanha:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                with col9:
                    st.metric("ROI", f"{roi:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

                if not df_pagamentos_campanha.empty:
                    st.subheader(f"Pagamentos por Dia Após o Envio (Janela de {janela_dias} dias)")

                    pagamentos_por_dia = df_pagamentos_campanha.groupby('DIAS_APOS_ENVIO')['VALOR_PAGO'].sum().reset_index()
                    pagamentos_por_dia.rename(columns={'DIAS_APOS_ENVIO': 'Dias Após Envio', 'VALOR_PAGO': 'Valor Total Pago'}, inplace=True)

                    fig_dias = px.bar(
                        pagamentos_por_dia,
                        x='Dias Após Envio', y='Valor Total Pago',
                        title='Valor Arrecadado por Dia Após o Envio',
                        labels={'Dias Após Envio': 'Dias Após o Envio', 'Valor Total Pago': 'Valor Total Pago (R$)'},
                        hover_data={'Valor Total Pago': ':.2f'}
                    )
                    fig_dias.update_layout(xaxis_title="Dias Após o Envio", yaxis_title="Valor Total Pago (R$)")
                    st.plotly_chart(fig_dias, use_container_width=True, key="fig_dias")

                    if 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:
                        st.subheader("Valor Arrecadado por Canal de Pagamento")

                        pagamentos_por_canal = df_pagamentos_campanha.groupby('TIPO_PAGAMENTO')['VALOR_PAGO'].sum().reset_index()
                        pagamentos_por_canal = pagamentos_por_canal.sort_values('VALOR_PAGO', ascending=False)

                        fig_canal = px.bar(
                            pagamentos_por_canal,
                            x='TIPO_PAGAMENTO', y='VALOR_PAGO',
                            title='Valor Arrecadado por Canal de Pagamento',
                            labels={'TIPO_PAGAMENTO': 'Canal de Pagamento', 'VALOR_PAGO': 'Valor Total Pago (R$)'},
                            color='TIPO_PAGAMENTO',
                            hover_data={'VALOR_PAGO': ':.2f'}
                        )
                        fig_canal.update_layout(xaxis_title="Canal de Pagamento", yaxis_title="Valor Total Pago (R$)", showlegend=False)
                        st.plotly_chart(fig_canal, use_container_width=True, key="fig_canal_aba1")
                else:
                    st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

            # ══════════════════════════════════════════════════
            # ABA 2 — CIDADE E DIRETORIA
            # ══════════════════════════════════════════════════
            with aba2:
                if not df_pagamentos_campanha.empty:
                    tem_cidade    = 'CIDADE' in df_pagamentos_campanha.columns
                    tem_diretoria = 'DIRETORIA' in df_pagamentos_campanha.columns

                    if tem_cidade:
                        st.subheader("Análise por Cidade")

                        cidade_resumo = df_pagamentos_campanha.groupby('CIDADE').agg(
                            Clientes_que_Pagaram=('MATRICULA', 'nunique'),
                            Valor_Arrecadado=('VALOR_PAGO', 'sum')
                        ).reset_index().sort_values('Valor_Arrecadado', ascending=False)

                        fig_cidade_valor = px.bar(
                            cidade_resumo,
                            x='CIDADE', y='Valor_Arrecadado',
                            title='Valor Arrecadado por Cidade',
                            labels={'CIDADE': 'Cidade', 'Valor_Arrecadado': 'Valor Arrecadado (R$)'},
                            hover_data={'Valor_Arrecadado': ':.2f'}
                        )
                        fig_cidade_valor.update_layout(xaxis_title="Cidade", yaxis_title="Valor Arrecadado (R$)")
                        st.plotly_chart(fig_cidade_valor, use_container_width=True, key="fig_cidade_valor")

                        fig_cidade_clientes = px.bar(
                            cidade_resumo,
                            x='CIDADE', y='Clientes_que_Pagaram',
                            title='Clientes que Pagaram por Cidade',
                            labels={'CIDADE': 'Cidade', 'Clientes_que_Pagaram': 'Clientes que Pagaram'}
                        )
                        fig_cidade_clientes.update_layout(xaxis_title="Cidade", yaxis_title="Clientes que Pagaram")
                        st.plotly_chart(fig_cidade_clientes, use_container_width=True, key="fig_cidade_clientes")

                        if 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:
                            st.subheader("Tipo de Pagamento por Cidade")
                            cidade_canal = df_pagamentos_campanha.groupby(['CIDADE', 'TIPO_PAGAMENTO'])['VALOR_PAGO'].sum().reset_index()
                            fig_cidade_canal = px.bar(
                                cidade_canal,
                                x='CIDADE', y='VALOR_PAGO', color='TIPO_PAGAMENTO',
                                title='Valor Pago por Cidade e Canal de Pagamento',
                                labels={'CIDADE': 'Cidade', 'VALOR_PAGO': 'Valor Pago (R$)', 'TIPO_PAGAMENTO': 'Canal'},
                                barmode='stack'
                            )
                            fig_cidade_canal.update_layout(xaxis_title="Cidade", yaxis_title="Valor Pago (R$)")
                            st.plotly_chart(fig_cidade_canal, use_container_width=True, key="fig_cidade_canal")

                    if tem_diretoria:
                        st.subheader("Análise por Diretoria")

                        diretoria_resumo = df_pagamentos_campanha.groupby('DIRETORIA').agg(
                            Clientes_que_Pagaram=('MATRICULA', 'nunique'),
                            Valor_Arrecadado=('VALOR_PAGO', 'sum')
                        ).reset_index().sort_values('Valor_Arrecadado', ascending=False)

                        fig_diretoria_valor = px.bar(
                            diretoria_resumo,
                            x='DIRETORIA', y='Valor_Arrecadado',
                            title='Valor Arrecadado por Diretoria',
                            labels={'DIRETORIA': 'Diretoria', 'Valor_Arrecadado': 'Valor Arrecadado (R$)'},
                            hover_data={'Valor_Arrecadado': ':.2f'}
                        )
                        fig_diretoria_valor.update_layout(xaxis_title="Diretoria", yaxis_title="Valor Arrecadado (R$)")
                        st.plotly_chart(fig_diretoria_valor, use_container_width=True, key="fig_diretoria_valor")

                        fig_diretoria_clientes = px.bar(
                            diretoria_resumo,
                            x='DIRETORIA', y='Clientes_que_Pagaram',
                            title='Clientes que Pagaram por Diretoria',
                            labels={'DIRETORIA': 'Diretoria', 'Clientes_que_Pagaram': 'Clientes que Pagaram'}
                        )
                        fig_diretoria_clientes.update_layout(xaxis_title="Diretoria", yaxis_title="Clientes que Pagaram")
                        st.plotly_chart(fig_diretoria_clientes, use_container_width=True, key="fig_diretoria_clientes")

                        if 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:
                            st.subheader("Tipo de Pagamento por Diretoria")
                            diretoria_canal = df_pagamentos_campanha.groupby(['DIRETORIA', 'TIPO_PAGAMENTO'])['VALOR_PAGO'].sum().reset_index()
                            fig_diretoria_canal = px.bar(
                                diretoria_canal,
                                x='DIRETORIA', y='VALOR_PAGO', color='TIPO_PAGAMENTO',
                                title='Valor Pago por Diretoria e Canal de Pagamento',
                                labels={'DIRETORIA': 'Diretoria', 'VALOR_PAGO': 'Valor Pago (R$)', 'TIPO_PAGAMENTO': 'Canal'},
                                barmode='stack'
                            )
                            fig_diretoria_canal.update_layout(xaxis_title="Diretoria", yaxis_title="Valor Pago (R$)")
                            st.plotly_chart(fig_diretoria_canal, use_container_width=True, key="fig_diretoria_canal")

                    if not tem_cidade and not tem_diretoria:
                        st.info("Colunas 'CIDADE' e 'DIRETORIA' não encontradas na base de clientes.")
                else:
                    st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

            # ══════════════════════════════════════════════════
            # ABA 3 — ANÁLISE DAS FATURAS
            # ══════════════════════════════════════════════════
            with aba3:
                if not df_pagamentos_campanha.empty:

                    if 'VENCIMENTO' in df_pagamentos_campanha.columns:
                        st.subheader("Antiguidade da Dívida Paga")

                        df_pagamentos_campanha['ANTIGUIDADE_DIAS'] = (
                            df_pagamentos_campanha['DATA_PAGAMENTO'] - df_pagamentos_campanha['VENCIMENTO']
                        ).dt.days

                        def classificar_antiguidade(dias):
                            if pd.isna(dias):
                                return 'Não informado'
                            elif dias <= 10:
                                return '0-10 dias'
                            elif dias <= 20:
                                return '11-20 dias'
                            elif dias <= 30:
                                return '21-30 dias'
                            elif dias <= 60:
                                return '31-60 dias'
                            else:
                                return 'Mais de 61 dias'

                        df_pagamentos_campanha['FAIXA_ANTIGUIDADE'] = df_pagamentos_campanha['ANTIGUIDADE_DIAS'].apply(classificar_antiguidade)

                        ordem_faixas = ['0-10 dias', '11-20 dias', '21-30 dias', '31-60 dias', 'Mais de 61 dias', 'Não informado']

                        antiguidade_resumo = df_pagamentos_campanha.groupby('FAIXA_ANTIGUIDADE').agg(
                            Quantidade=('MATRICULA', 'count'),
                            Valor_Pago=('VALOR_PAGO', 'sum')
                        ).reset_index()
                        antiguidade_resumo['FAIXA_ANTIGUIDADE'] = pd.Categorical(
                            antiguidade_resumo['FAIXA_ANTIGUIDADE'], categories=ordem_faixas, ordered=True
                        )
                        antiguidade_resumo = antiguidade_resumo.sort_values('FAIXA_ANTIGUIDADE')

                        fig_ant_valor = px.bar(
                            antiguidade_resumo,
                            x='FAIXA_ANTIGUIDADE', y='Valor_Pago',
                            title='Valor Pago por Faixa de Antiguidade da Dívida',
                            labels={'FAIXA_ANTIGUIDADE': 'Faixa de Antiguidade', 'Valor_Pago': 'Valor Pago (R$)'},
                            hover_data={'Valor_Pago': ':.2f'}
                        )
                        fig_ant_valor.update_layout(xaxis_title="Faixa de Antiguidade", yaxis_title="Valor Pago (R$)")
                        st.plotly_chart(fig_ant_valor, use_container_width=True, key="fig_ant_valor")

                        fig_ant_qtd = px.bar(
                            antiguidade_resumo,
                            x='FAIXA_ANTIGUIDADE', y='Quantidade',
                            title='Quantidade de Pagamentos por Faixa de Antiguidade',
                            labels={'FAIXA_ANTIGUIDADE': 'Faixa de Antiguidade', 'Quantidade': 'Quantidade de Pagamentos'}
                        )
                        fig_ant_qtd.update_layout(xaxis_title="Faixa de Antiguidade", yaxis_title="Quantidade de Pagamentos")
                        st.plotly_chart(fig_ant_qtd, use_container_width=True, key="fig_ant_qtd")

                    if 'MES_ANO_FATURA' in df_pagamentos_campanha.columns:
                        st.subheader("Valor Pago por Mês/Ano da Fatura")

                        mes_ano_resumo = df_pagamentos_campanha.groupby(
                            ['ANO_FATURA', 'MES_FATURA', 'MES_ANO_FATURA']
                        )['VALOR_PAGO'].sum().reset_index()
                        mes_ano_resumo = mes_ano_resumo.sort_values(['ANO_FATURA', 'MES_FATURA'])

                        fig_mes_ano = px.bar(
                            mes_ano_resumo,
                            x='MES_ANO_FATURA', y='VALOR_PAGO',
                            title='Valor Pago por Mês/Ano da Fatura',
                            labels={'MES_ANO_FATURA': 'Mês/Ano da Fatura', 'VALOR_PAGO': 'Valor Pago (R$)'},
                            hover_data={'VALOR_PAGO': ':.2f'}
                        )
                        fig_mes_ano.update_layout(xaxis_title="Mês/Ano da Fatura", yaxis_title="Valor Pago (R$)")
                        st.plotly_chart(fig_mes_ano, use_container_width=True, key="fig_mes_ano")

                    if 'TIPO_FATURA' in df_pagamentos_campanha.columns:
                        st.subheader("Valor Pago por Tipo de Fatura")

                        tipo_fatura_resumo = df_pagamentos_campanha.groupby('TIPO_FATURA').agg(
                            Quantidade=('MATRICULA', 'count'),
                            Valor_Pago=('VALOR_PAGO', 'sum')
                        ).reset_index().sort_values('Valor_Pago', ascending=False)

                        fig_tipo_fatura = px.bar(
                            tipo_fatura_resumo,
                            x='TIPO_FATURA', y='Valor_Pago',
                            title='Valor Pago por Tipo de Fatura',
                            labels={'TIPO_FATURA': 'Tipo de Fatura', 'Valor_Pago': 'Valor Pago (R$)'},
                            color='TIPO_FATURA',
                            hover_data={'Valor_Pago': ':.2f', 'Quantidade': True}
                        )
                        fig_tipo_fatura.update_layout(xaxis_title="Tipo de Fatura", yaxis_title="Valor Pago (R$)", showlegend=False)
                        st.plotly_chart(fig_tipo_fatura, use_container_width=True, key="fig_tipo_fatura")

                    if 'UTILIZACAO' in df_pagamentos_campanha.columns:
                        st.subheader("Valor Pago por Utilização (Sub. Categoria)")

                        utilizacao_resumo = df_pagamentos_campanha.groupby('UTILIZACAO').agg(
                            Quantidade=('MATRICULA', 'count'),
                            Valor_Pago=('VALOR_PAGO', 'sum')
                        ).reset_index().sort_values('Valor_Pago', ascending=False)

                        fig_utilizacao = px.bar(
                            utilizacao_resumo,
                            x='UTILIZACAO', y='Valor_Pago',
                            title='Valor Pago por Utilização (Sub. Categoria)',
                            labels={'UTILIZACAO': 'Utilização', 'Valor_Pago': 'Valor Pago (R$)'},
                            color='UTILIZACAO',
                            hover_data={'Valor_Pago': ':.2f', 'Quantidade': True}
                        )
                        fig_utilizacao.update_layout(xaxis_title="Utilização", yaxis_title="Valor Pago (R$)", showlegend=False)
                        st.plotly_chart(fig_utilizacao, use_container_width=True, key="fig_utilizacao")

                else:
                    st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

            # ══════════════════════════════════════════════════
            # ABA 4 — CANAL DE PAGAMENTO
            # ══════════════════════════════════════════════════
            with aba4:
                if not df_pagamentos_campanha.empty and 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:

                    st.subheader("Valor Arrecadado por Canal de Pagamento")

                    pagamentos_por_canal = df_pagamentos_campanha.groupby('TIPO_PAGAMENTO')['VALOR_PAGO'].sum().reset_index()
                    pagamentos_por_canal = pagamentos_por_canal.sort_values('VALOR_PAGO', ascending=False)

                    fig_canal = px.bar(
                        pagamentos_por_canal,
                        x='TIPO_PAGAMENTO', y='VALOR_PAGO',
                        title='Valor Arrecadado por Canal de Pagamento',
                        labels={'TIPO_PAGAMENTO': 'Canal de Pagamento', 'VALOR_PAGO': 'Valor Total Pago (R$)'},
                        color='TIPO_PAGAMENTO',
                        hover_data={'VALOR_PAGO': ':.2f'}
                    )
                    fig_canal.update_layout(xaxis_title="Canal de Pagamento", yaxis_title="Valor Total Pago (R$)", showlegend=False)
                    st.plotly_chart(fig_canal, use_container_width=True, key="fig_canal_aba4")

                    st.subheader("Clientes que Pagaram por Canal")

                    qtd_por_canal = df_pagamentos_campanha.groupby('TIPO_PAGAMENTO')['MATRICULA'].nunique().reset_index()
                    qtd_por_canal.rename(columns={'MATRICULA': 'Clientes que Pagaram'}, inplace=True)
                    qtd_por_canal = qtd_por_canal.sort_values('Clientes que Pagaram', ascending=False)

                    fig_canal_qtd = px.bar(
                        qtd_por_canal,
                        x='TIPO_PAGAMENTO', y='Clientes que Pagaram',
                        title='Clientes que Pagaram por Canal',
                        labels={'TIPO_PAGAMENTO': 'Canal de Pagamento', 'Clientes que Pagaram': 'Clientes que Pagaram'},
                        color='TIPO_PAGAMENTO'
                    )
                    fig_canal_qtd.update_layout(xaxis_title="Canal de Pagamento", yaxis_title="Clientes que Pagaram", showlegend=False)
                    st.plotly_chart(fig_canal_qtd, use_container_width=True, key="fig_canal_qtd")

                else:
                    st.info("Coluna 'Tipo Pagamento' não encontrada no arquivo de pagamentos.")

            # ══════════════════════════════════════════════════
            # ABA 5 — DETALHES
            # ══════════════════════════════════════════════════
            with aba5:
                if not df_pagamentos_campanha.empty:
                    st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")

                    colunas_possiveis = [
                        'MATRICULA', 'CIDADE', 'DIRETORIA', 'TELEFONE_ENVIO',
                        'DATA_ENVIO', 'DATA_PAGAMENTO', 'VENCIMENTO',
                        'VALOR_PAGO', 'DIAS_APOS_ENVIO',
                        'TIPO_FATURA', 'UTILIZACAO', 'TIPO_PAGAMENTO'
                    ]
                    colunas_exibicao = [c for c in colunas_possiveis if c in df_pagamentos_campanha.columns]

                    df_detalhes = df_pagamentos_campanha[colunas_exibicao].drop_duplicates(
                        subset=['MATRICULA', 'DATA_PAGAMENTO', 'VALOR_PAGO']
                    )

                    st.dataframe(df_detalhes)

                    csv_output = df_detalhes.to_csv(index=False, sep=';', decimal=',')
                    st.download_button(
                        label="Baixar Detalhes dos Pagamentos da Campanha (CSV)",
                        data=csv_output,
                        file_name="pagamentos_campanha.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

        else:
            st.error("Não foi possível processar um ou mais arquivos. Verifique os formatos e as colunas esperadas ou se há matrículas válidas após o cruzamento.")
    else:
        st.warning("Por favor, carregue todos os três arquivos para iniciar a análise.")
