import streamlit as st
import pandas as pd
from datetime import timedelta
import plotly.express as px

# Configurações da página do Streamlit
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
            raise ValueError("Formato de arquivo de pagamentos não suportado. Use .csv ou .xlsx.")

        if df is None or df.empty:
            st.sidebar.error("Arquivo de Pagamentos está vazio ou não pôde ser lido.")
            return None

        if df.shape[1] < 10:
            st.sidebar.error(f"Arquivo de Pagamentos: Esperava pelo menos 10 colunas, mas encontrou {df.shape[1]}.")
            return None

        # -------------------------------------------------------
        # ÍNDICES DAS COLUNAS - ajuste conforme seu arquivo:
        # 0  = Matrícula
        # 6  = Data Pagamento
        # 9  = Valor Pago
        # 18 = Tipo Pagamento
        # 5  = Vencimento          <-- CONFIRME ESTE ÍNDICE
        # 11 = Tipo Fatura         <-- CONFIRME ESTE ÍNDICE
        # 15 = Utilização (Sub. Categ.) <-- CONFIRME ESTE ÍNDICE
        # -------------------------------------------------------

        IDX_MATRICULA   = 0
        IDX_VENCIMENTO  = 4   # <-- ajuste se necessário
        IDX_DT_PGTO     = 5
        IDX_VALOR       = 3
        IDX_TIPO_FATURA = 11  # <-- ajuste se necessário
        IDX_UTILIZACAO  = 9  # <-- ajuste se necessário
        IDX_TIPO_PGTO   = 12  # <-- ajuste se necessário

        col_indices = [IDX_MATRICULA, IDX_VENCIMENTO, IDX_DT_PGTO, IDX_VALOR]
        col_names   = ['MATRICULA_PAGAMENTO', 'VENCIMENTO', 'DATA_PAGAMENTO', 'VALOR_PAGO']

        if df.shape[1] > IDX_TIPO_FATURA:
            col_indices.append(IDX_TIPO_FATURA)
            col_names.append('TIPO_FATURA')

        if df.shape[1] > IDX_UTILIZACAO:
            col_indices.append(IDX_UTILIZACAO)
            col_names.append('UTILIZACAO')

        if df.shape[1] > IDX_TIPO_PGTO:
            col_indices.append(IDX_TIPO_PGTO)
            col_names.append('TIPO_PAGAMENTO')

        df_pagamentos = df.iloc[:, col_indices].copy()
        df_pagamentos.columns = col_names

        df_pagamentos['MATRICULA_PAGAMENTO'] = df_pagamentos['MATRICULA_PAGAMENTO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        df_pagamentos['DATA_PAGAMENTO'] = pd.to_datetime(df_pagamentos['DATA_PAGAMENTO'], errors='coerce', dayfirst=True)
        df_pagamentos.dropna(subset=['DATA_PAGAMENTO'], inplace=True)

        df_pagamentos['VENCIMENTO'] = pd.to_datetime(df_pagamentos['VENCIMENTO'], errors='coerce', dayfirst=True)

        df_pagamentos['VALOR_PAGO'] = df_pagamentos['VALOR_PAGO'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df_pagamentos['VALOR_PAGO'] = pd.to_numeric(df_pagamentos['VALOR_PAGO'], errors='coerce')
        df_pagamentos.dropna(subset=['VALOR_PAGO'], inplace=True)

        # Criar colunas de Mês e Ano a partir da data de vencimento
        df_pagamentos['MES_FATURA']  = df_pagamentos['VENCIMENTO'].dt.month
        df_pagamentos['ANO_FATURA']  = df_pagamentos['VENCIMENTO'].dt.year
        df_pagamentos['MES_ANO_FATURA'] = df_pagamentos['VENCIMENTO'].dt.strftime('%m/%Y')

        for col in ['TIPO_FATURA', 'UTILIZACAO', 'TIPO_PAGAMENTO']:
            if col in df_pagamentos.columns:
                df_pagamentos[col] = df_pagamentos[col].astype(str).str.strip()
                df_pagamentos[col] = df_pagamentos[col].replace('nan', 'Não informado')

        st.sidebar.success("Arquivo de Pagamentos processado com sucesso!")
        return df_pagamentos
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Pagamentos: {e}")
        return None

@st.cache_data
def load_and_process_clientes(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file)

        required_cols = ['TELEFONE', 'MATRICULA', 'SITUACAO', 'CIDADE', 'DIRETORIA']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Arquivo de Clientes: Colunas esperadas não encontradas. Verifique se existem as colunas: {required_cols}")
            return None

        df_clientes = df[['TELEFONE', 'MATRICULA', 'SITUACAO', 'CIDADE', 'DIRETORIA']].copy()
        df_clientes.rename(columns={
            'TELEFONE': 'TELEFONE_CLIENTE',
            'MATRICULA': 'MATRICULA_CLIENTE'
        }, inplace=True)

        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].astype(str).str.replace(r'^55', '', regex=True).str.replace(r'\.0$', '', regex=True)
        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].str.strip()

        df_clientes['MATRICULA_CLIENTE'] = df_clientes['MATRICULA_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        df_clientes['SITUACAO'] = pd.to_numeric(df_clientes['SITUACAO'], errors='coerce').fillna(0)

        df_clientes['CIDADE']    = df_clientes['CIDADE'].astype(str).str.strip()
        df_clientes['DIRETORIA'] = df_clientes['DIRETORIA'].astype(str).str.strip()

        df_clientes.drop_duplicates(subset=['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE'], inplace=True)

        st.sidebar.success("Arquivo de Clientes processado com sucesso!")
        return df_clientes
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Clientes: {e}")
        return None

# --- Interface Streamlit ---

st.sidebar.header("Upload de Arquivos")
uploaded_envios    = st.sidebar.file_uploader("1. Base de Envios (Notificações - .xlsx)", type=["xlsx"])
uploaded_pagamentos = st.sidebar.file_uploader("2. Base de Pagamentos (.csv ou .xlsx)", type=["csv", "xlsx"])
uploaded_clientes  = st.sidebar.file_uploader("3. Base de Identificação de Clientes (.xlsx)", type=["xlsx"])

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

        # Total de clientes notificados = telefones únicos direto do df_envios
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

        # 1. Cruzar Envios com Clientes para obter Matrícula, Cidade e Diretoria
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

            clientes_que_pagaram_matriculas = df_pagamentos_campanha['MATRICULA'].nunique()
            valor_total_arrecadado  = df_pagamentos_campanha['VALOR_PAGO'].sum() if not df_pagamentos_campanha.empty else 0
            taxa_eficiencia_clientes = (clientes_que_pagaram_matriculas / total_clientes_notificados * 100) if total_clientes_notificados > 0 else 0
            taxa_eficiencia_valor    = (valor_total_arrecadado / total_divida_notificados * 100) if total_divida_notificados > 0 else 0
            ticket_medio             = (valor_total_arrecadado / clientes_que_pagaram_matriculas) if clientes_que_pagaram_matriculas > 0 else 0

            # ── ABAS ──────────────────────────────────────────────
            aba1, aba2, aba3, aba4, aba5 = st.tabs([
                "📊 Visão Geral",
                "🏙️ Cidade e Diretoria",
                "📅 Análise das Faturas",
                "💳 Canal de Pagamento",
                "📋 Detalhes"
            ])

            # ══════════════════════════════════════════════════════
            # ABA 1 — VISÃO GERAL
            # ══════════════════════════════════════════════════════
            with aba1:
                st.subheader("Resultados da Análise da Campanha")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total de clientes notificados", f"{total_clientes_notificados}")
                with col2:
                    st.metric("Clientes que pagaram na janela", f"{clientes_que_pagaram_matriculas}")
                with col3:
                    st.metric("Taxa de eficiência (clientes)", f"{taxa_eficiencia_clientes:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))
                with col4:
                    st.metric("Ticket médio", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

                col5, col6, col7 = st.columns(3)
                with col5:
                    st.metric("Valor total arrecadado na campanha", f"R$ {valor_total_arrecadado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                with col6:
                    st.metric("Total da dívida dos notificados", f"R$ {total_divida_notificados:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                with col7:
                    st.metric("Taxa de eficiência (valor)", f"{taxa_eficiencia_valor:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

                if not df_pagamentos_campanha.empty:
                    st.subheader(f"Pagamentos por Dia Após o Envio (Janela de {janela_dias} dias)")

                    df_pagamentos_campanha['DIAS_APOS_ENVIO'] = (
                        df_pagamentos_campanha['DATA_PAGAMENTO'] - df_pagamentos_campanha['DATA_ENVIO']
                    ).dt.days

                    pagamentos_por_dia = df_pagamentos_campanha.groupby('DIAS_APOS_ENVIO')['VALOR_PAGO'].sum().reset_index()
                    pagamentos_por_dia.rename(columns={'DIAS_APOS_ENVIO': 'Dias Após Envio', 'VALOR_PAGO': 'Valor Total Pago'}, inplace=True)

                    fig_dias = px.bar(
                        pagamentos_por_dia,
                        x='Dias Após Envio',
                        y='Valor Total Pago',
                        title='Valor Arrecadado por Dia Após o Envio',
                        labels={'Dias Após Envio': 'Dias Após o Envio', 'Valor Total Pago': 'Valor Total Pago (R$)'},
                        hover_data={'Valor Total Pago': ':.2f'}
                    )
                    fig_dias.update_layout(xaxis_title="Dias Após o Envio", yaxis_title="Valor Total Pago (R$)")
                    st.plotly_chart(fig_dias, use_container_width=True)

            # ══════════════════════════════════════════════════════
            # ABA 2 — CIDADE E DIRETORIA
            # ══════════════════════════════════════════════════════
            with aba2:
                if not df_pagamentos_campanha.empty:

                    # --- CIDADE ---
                    st.subheader("Análise por Cidade")

                    cidade_resumo = df_pagamentos_campanha.groupby('CIDADE').agg(
                        Clientes_que_Pagaram=('MATRICULA', 'nunique'),
                        Valor_Arrecadado=('VALOR_PAGO', 'sum')
                    ).reset_index().sort_values('Valor_Arrecadado', ascending=False)
                    cidade_resumo.rename(columns={'CIDADE': 'Cidade'}, inplace=True)

                    fig_cidade_valor = px.bar(
                        cidade_resumo,
                        x='Cidade',
                        y='Valor_Arrecadado',
                        title='Valor Arrecadado por Cidade',
                        labels={'Cidade': 'Cidade', 'Valor_Arrecadado': 'Valor Arrecadado (R$)'},
                        hover_data={'Valor_Arrecadado': ':.2f'}
                    )
                    fig_cidade_valor.update_layout(xaxis_title="Cidade", yaxis_title="Valor Arrecadado (R$)")
                    st.plotly_chart(fig_cidade_valor, use_container_width=True)

                    fig_cidade_clientes = px.bar(
                        cidade_resumo,
                        x='Cidade',
                        y='Clientes_que_Pagaram',
                        title='Quantidade de Clientes que Pagaram por Cidade',
                        labels={'Cidade': 'Cidade', 'Clientes_que_Pagaram': 'Clientes que Pagaram'},
                    )
                    fig_cidade_clientes.update_layout(xaxis_title="Cidade", yaxis_title="Clientes que Pagaram")
                    st.plotly_chart(fig_cidade_clientes, use_container_width=True)

                    # Tipo de pagamento por cidade
                    if 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:
                        st.subheader("Tipo de Pagamento mais Utilizado por Cidade")
                        cidade_canal = df_pagamentos_campanha.groupby(['CIDADE', 'TIPO_PAGAMENTO'])['VALOR_PAGO'].sum().reset_index()
                        cidade_canal.rename(columns={'CIDADE': 'Cidade', 'TIPO_PAGAMENTO': 'Canal', 'VALOR_PAGO': 'Valor Pago'}, inplace=True)

                        fig_cidade_canal = px.bar(
                            cidade_canal,
                            x='Cidade',
                            y='Valor Pago',
                            color='Canal',
                            title='Valor Pago por Cidade e Canal de Pagamento',
                            labels={'Cidade': 'Cidade', 'Valor Pago': 'Valor Pago (R$)', 'Canal': 'Canal de Pagamento'},
                            barmode='stack'
                        )
                        fig_cidade_canal.update_layout(xaxis_title="Cidade", yaxis_title="Valor Pago (R$)")
                        st.plotly_chart(fig_cidade_canal, use_container_width=True)

                    # --- DIRETORIA ---
                    st.subheader("Análise por Diretoria")

                    diretoria_resumo = df_pagamentos_campanha.groupby('DIRETORIA').agg(
                        Clientes_que_Pagaram=('MATRICULA', 'nunique'),
                        Valor_Arrecadado=('VALOR_PAGO', 'sum')
                    ).reset_index().sort_values('Valor_Arrecadado', ascending=False)
                    diretoria_resumo.rename(columns={'DIRETORIA': 'Diretoria'}, inplace=True)

                    fig_diretoria_valor = px.bar(
                        diretoria_resumo,
                        x='Diretoria',
                        y='Valor_Arrecadado',
                        title='Valor Arrecadado por Diretoria',
                        labels={'Diretoria': 'Diretoria', 'Valor_Arrecadado': 'Valor Arrecadado (R$)'},
                        hover_data={'Valor_Arrecadado': ':.2f'}
                    )
                    fig_diretoria_valor.update_layout(xaxis_title="Diretoria", yaxis_title="Valor Arrecadado (R$)")
                    st.plotly_chart(fig_diretoria_valor, use_container_width=True)

                    fig_diretoria_clientes = px.bar(
                        diretoria_resumo,
                        x='Diretoria',
                        y='Clientes_que_Pagaram',
                        title='Quantidade de Clientes que Pagaram por Diretoria',
                        labels={'Diretoria': 'Diretoria', 'Clientes_que_Pagaram': 'Clientes que Pagaram'},
                    )
                    fig_diretoria_clientes.update_layout(xaxis_title="Diretoria", yaxis_title="Clientes que Pagaram")
                    st.plotly_chart(fig_diretoria_clientes, use_container_width=True)

                    # Tipo de pagamento por diretoria
                    if 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:
                        st.subheader("Tipo de Pagamento mais Utilizado por Diretoria")
                        diretoria_canal = df_pagamentos_campanha.groupby(['DIRETORIA', 'TIPO_PAGAMENTO'])['VALOR_PAGO'].sum().reset_index()
                        diretoria_canal.rename(columns={'DIRETORIA': 'Diretoria', 'TIPO_PAGAMENTO': 'Canal', 'VALOR_PAGO': 'Valor Pago'}, inplace=True)

                        fig_diretoria_canal = px.bar(
                            diretoria_canal,
                            x='Diretoria',
                            y='Valor Pago',
                            color='Canal',
                            title='Valor Pago por Diretoria e Canal de Pagamento',
                            labels={'Diretoria': 'Diretoria', 'Valor Pago': 'Valor Pago (R$)', 'Canal': 'Canal de Pagamento'},
                            barmode='stack'
                        )
                        fig_diretoria_canal.update_layout(xaxis_title="Diretoria", yaxis_title="Valor Pago (R$)")
                        st.plotly_chart(fig_diretoria_canal, use_container_width=True)

                else:
                    st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

            # ══════════════════════════════════════════════════════
            # ABA 3 — ANÁLISE DAS FATURAS
            # ══════════════════════════════════════════════════════
            with aba3:
                if not df_pagamentos_campanha.empty:

                    # Antiguidade da dívida (Vencimento)
                    if 'VENCIMENTO' in df_pagamentos_campanha.columns:
                        st.subheader("Antiguidade da Dívida Paga (Data de Vencimento)")

                        df_pagamentos_campanha['ANTIGUIDADE_DIAS'] = (
                            df_pagamentos_campanha['DATA_PAGAMENTO'] - df_pagamentos_campanha['VENCIMENTO']
                        ).dt.days

                        # Agrupar por faixas de antiguidade
                        def classificar_antiguidade(dias):
                            if pd.isna(dias):
                                return 'Não informado'
                            elif dias <= 30:
                                return '0-30 dias'
                            elif dias <= 60:
                                return '31-60 dias'
                            elif dias <= 90:
                                return '61-90 dias'
                            elif dias <= 180:
                                return '91-180 dias'
                            elif dias <= 365:
                                return '181-365 dias'
                            else:
                                return 'Mais de 1 ano'

                        df_pagamentos_campanha['FAIXA_ANTIGUIDADE'] = df_pagamentos_campanha['ANTIGUIDADE_DIAS'].apply(classificar_antiguidade)

                        ordem_faixas = ['0-30 dias', '31-60 dias', '61-90 dias', '91-180 dias', '181-365 dias', 'Mais de 1 ano', 'Não informado']

                        antiguidade_resumo = df_pagamentos_campanha.groupby('FAIXA_ANTIGUIDADE').agg(
                            Quantidade=('MATRICULA', 'count'),
                            Valor_Pago=('VALOR_PAGO', 'sum')
                        ).reset_index()
                        antiguidade_resumo['FAIXA_ANTIGUIDADE'] = pd.Categorical(antiguidade_resumo['FAIXA_ANTIGUIDADE'], categories=ordem_faixas, ordered=True)
                        antiguidade_resumo = antiguidade_resumo.sort_values('FAIXA_ANTIGUIDADE')

                        fig_antiguidade_valor = px.bar(
                            antiguidade_resumo,
                            x='FAIXA_ANTIGUIDADE',
                            y='Valor_Pago',
                            title='Valor Pago por Faixa de Antiguidade da Dívida',
                            labels={'FAIXA_ANTIGUIDADE': 'Faixa de Antiguidade', 'Valor_Pago': 'Valor Pago (R$)'},
                            hover_data={'Valor_Pago': ':.2f'}
                        )
                        fig_antiguidade_valor.update_layout(xaxis_title="Faixa de Antiguidade", yaxis_title="Valor Pago (R$)")
                        st.plotly_chart(fig_antiguidade_valor, use_container_width=True)

                        fig_antiguidade_qtd = px.bar(
                            antiguidade_resumo,
                            x='FAIXA_ANTIGUIDADE',
                            y='Quantidade',
                            title='Quantidade de Pagamentos por Faixa de Antiguidade da Dívida',
                            labels={'FAIXA_ANTIGUIDADE': 'Faixa de Antiguidade', 'Quantidade': 'Quantidade de Pagamentos'},
                        )
                        fig_antiguidade_qtd.update_layout(xaxis_title="Faixa de Antiguidade", yaxis_title="Quantidade de Pagamentos")
                        st.plotly_chart(fig_antiguidade_qtd, use_container_width=True)

                    # Mês e Ano da fatura
                    if 'MES_ANO_FATURA' in df_pagamentos_campanha.columns:
                        st.subheader("Valor Pago por Mês/Ano da Fatura")

                        mes_ano_resumo = df_pagamentos_campanha.groupby(['ANO_FATURA', 'MES_FATURA', 'MES_ANO_FATURA'])['VALOR_PAGO'].sum().reset_index()
                        mes_ano_resumo = mes_ano_resumo.sort_values(['ANO_FATURA', 'MES_FATURA'])

                        fig_mes_ano = px.bar(
                            mes_ano_resumo,
                            x='MES_ANO_FATURA',
                            y='VALOR_PAGO',
                            title='Valor Pago por Mês/Ano da Fatura',
                            labels={'MES_ANO_FATURA': 'Mês/Ano da Fatura', 'VALOR_PAGO': 'Valor Pago (R$)'},
                            hover_data={'VALOR_PAGO': ':.2f'}
                        )
                        fig_mes_ano.update_layout(xaxis_title="Mês/Ano da Fatura", yaxis_title="Valor Pago (R$)")
                        st.plotly_chart(fig_mes_ano, use_container_width=True)

                    # Tipo Fatura
                    if 'TIPO_FATURA' in df_pagamentos_campanha.columns:
                        st.subheader("Valor Pago por Tipo de Fatura")

                        tipo_fatura_resumo = df_pagamentos_campanha.groupby('TIPO_FATURA').agg(
                            Quantidade=('MATRICULA', 'count'),
                            Valor_Pago=('VALOR_PAGO', 'sum')
                        ).reset_index().sort_values('Valor_Pago', ascending=False)

                        fig_tipo_fatura = px.bar(
                            tipo_fatura_resumo,
                            x='TIPO_FATURA',
                            y='Valor_Pago',
                            title='Valor Pago por Tipo de Fatura',
                            labels={'TIPO_FATURA': 'Tipo de Fatura', 'Valor_Pago': 'Valor Pago (R$)'},
                            color='TIPO_FATURA',
                            hover_data={'Valor_Pago': ':.2f', 'Quantidade': True}
                        )
                        fig_tipo_fatura.update_layout(xaxis_title="Tipo de Fatura", yaxis_title="Valor Pago (R$)", showlegend=False)
                        st.plotly_chart(fig_tipo_fatura, use_container_width=True)

                    # Utilização (Sub. Categ.)
                    if 'UTILIZACAO' in df_pagamentos_campanha.columns:
                        st.subheader("Valor Pago por Utilização (Sub. Categoria)")

                        utilizacao_resumo = df_pagamentos_campanha.groupby('UTILIZACAO').agg(
                            Quantidade=('MATRICULA', 'count'),
                            Valor_Pago=('VALOR_PAGO', 'sum')
                        ).reset_index().sort_values('Valor_Pago', ascending=False)

                        fig_utilizacao = px.bar(
                            utilizacao_resumo,
                            x='UTILIZACAO',
                            y='Valor_Pago',
                            title='Valor Pago por Utilização (Sub. Categoria)',
                            labels={'UTILIZACAO': 'Utilização', 'Valor_Pago': 'Valor Pago (R$)'},
                            color='UTILIZACAO',
                            hover_data={'Valor_Pago': ':.2f', 'Quantidade': True}
                        )
                        fig_utilizacao.update_layout(xaxis_title="Utilização", yaxis_title="Valor Pago (R$)", showlegend=False)
                        st.plotly_chart(fig_utilizacao, use_container_width=True)

                else:
                    st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

            # ══════════════════════════════════════════════════════
            # ABA 4 — CANAL DE PAGAMENTO
            # ══════════════════════════════════════════════════════
            with aba4:
                if not df_pagamentos_campanha.empty and 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:
                    st.subheader("Valor Arrecadado por Canal de Pagamento")

                    pagamentos_por_canal = df_pagamentos_campanha.groupby('TIPO_PAGAMENTO')['VALOR_PAGO'].sum().reset_index()
                    pagamentos_por_canal.rename(columns={'TIPO_PAGAMENTO': 'Canal de Pagamento', 'VALOR_PAGO': 'Valor Total Pago'}, inplace=True)
                    pagamentos_por_canal = pagamentos_por_canal.sort_values('Valor Total Pago', ascending=False)

                    fig_canal = px.bar(
                        pagamentos_por_canal,
                        x='Canal de Pagamento',
                        y='Valor Total Pago',
                        title='Valor Arrecadado por Canal de Pagamento',
                        labels={'Canal de Pagamento': 'Canal de Pagamento', 'Valor Total Pago': 'Valor Total Pago (R$)'},
                        color='Canal de Pagamento',
                        hover_data={'Valor Total Pago': ':.2f'}
                    )
                    fig_canal.update_layout(xaxis_title="Canal de Pagamento", yaxis_title="Valor Total Pago (R$)", showlegend=False)
                    st.plotly_chart(fig_canal, use_container_width=True)

                    # Quantidade de pagamentos por canal
                    qtd_por_canal = df_pagamentos_campanha.groupby('TIPO_PAGAMENTO')['MATRICULA'].nunique().reset_index()
                    qtd_por_canal.rename(columns={'TIPO_PAGAMENTO': 'Canal de Pagamento', 'MATRICULA': 'Clientes que Pagaram'}, inplace=True)
                    qtd_por_canal = qtd_por_canal.sort_values('Clientes que Pagaram', ascending=False)

                    fig_canal_qtd = px.bar(
                        qtd_por_canal,
                        x='Canal de Pagamento',
                        y='Clientes que Pagaram',
                        title='Quantidade de Clientes que Pagaram por Canal',
                        labels={'Canal de Pagamento': 'Canal de Pagamento', 'Clientes que Pagaram': 'Clientes que Pagaram'},
                        color='Canal de Pagamento'
                    )
                    fig_canal_qtd.update_layout(xaxis_title="Canal de Pagamento", yaxis_title="Clientes que Pagaram", showlegend=False)
                    st.plotly_chart(fig_canal_qtd, use_container_width=True)

                else:
                    st.info("Coluna 'Tipo Pagamento' não encontrada no arquivo de pagamentos.")

            # ══════════════════════════════════════════════════════
            # ABA 5 — DETALHES
            # ══════════════════════════════════════════════════════
            with aba5:
                if not df_pagamentos_campanha.empty:
                    st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")

                    colunas_exibicao = ['MATRICULA', 'CIDADE', 'DIRETORIA', 'TELEFONE_ENVIO', 'DATA_ENVIO', 'DATA_PAGAMENTO', 'VENCIMENTO', 'VALOR_PAGO', 'DIAS_APOS_ENVIO']
                    for col in ['TIPO_FATURA', 'UTILIZACAO', 'TIPO_PAGAMENTO']:
                        if col in df_pagamentos_campanha.columns:
                            colunas_exibicao.append(col)

                    # Manter apenas colunas que existem no dataframe
                    colunas_exibicao = [c for c in colunas_exibicao if c in df_pagamentos_campanha.columns]

                    df_detalhes_pagamentos = df_pagamentos_campanha[colunas_exibicao].drop_duplicates(
                        subset=['MATRICULA', 'DATA_PAGAMENTO', 'VALOR_PAGO']
                    )

                    st.dataframe(df_detalhes_pagamentos)

                    csv_output = df_detalhes_pagamentos.to_csv(index=False, sep=';', decimal=',')
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
