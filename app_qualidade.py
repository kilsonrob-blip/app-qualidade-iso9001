import os
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, Text, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# --- CONFIGURAÇÃO DO BANCO DE DADOS (SQLAlchemy) ---
Base = declarative_base()

class ProdutoModel(Base):
    """Tabela que armazena a listagem de produtos (Simulando a Planilha no Banco)"""
    __tablename__ = 'produtos'
    codigo = Column(String, primary_key=True)
    descricao = Column(String, nullable=False)

class NaoConformidadeModel(Base):
    __tablename__ = 'nao_conformidades'
    id_nc = Column(String, primary_key=True)
    data_identificacao = Column(DateTime, default=datetime.utcnow)
    descricao_saida = Column(Text, nullable=False)
    processo_origem = Column(String, nullable=False)
    responsavel_identificacao = Column(String, nullable=False)
    impacto_potencial = Column(String, nullable=False)
    status = Column(String, default="Identificado/Segregado")
    tratativa_adotada = Column(String, nullable=True)
    detalhes_tratativa = Column(Text, nullable=True)
    caminho_evidencia = Column(String, nullable=True)
    prazo_sla = Column(DateTime, nullable=False)
    
    # --- NOVOS CAMPOS ADICIONADOS ---
    codigo_produto = Column(String, nullable=False)
    descricao_produto = Column(String, nullable=False)
    quantidade_lote = Column(Float, nullable=False)
    quantidade_reprovada = Column(Float, nullable=False)
    numero_nota_fiscal = Column(String, nullable=False)
    
    # Campos da Causa Raiz (5 Porquês)
    porque_1 = Column(Text, nullable=True)
    porque_2 = Column(Text, nullable=True)
    porque_3 = Column(Text, nullable=True)
    porque_4 = Column(Text, nullable=True)
    porque_5 = Column(Text, nullable=True)
    causa_raiz_definida = Column(Text, nullable=True)
    
    autorizado_por = Column(String, nullable=True)
    data_fechamento = Column(DateTime, nullable=True)
    informacao_documentada_retida = Column(Boolean, default=False)

class AcoesPreventivasModel(Base):
    __tablename__ = 'acoes_preventivas'
    id_ap = Column(String, primary_key=True)
    data_abertura = Column(DateTime, default=datetime.utcnow)
    processo = Column(String, nullable=False)
    causa_raiz_gatilho = Column(Text, nullable=False)
    descricao_plano = Column(Text, nullable=False)
    status = Column(String, default="Aberta")

# Inicialização do Banco SQLite
engine = create_engine("sqlite:///iso9001_qualidade_v3.db", echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# --- CARGA INICIAL DE PRODUTOS (Simulação da Planilha de Fábrica) ---
def popular_produtos_se_vazio():
    session = Session()
    if session.query(ProdutoModel).count() == 0:
        produtos_padrao = [
            ProdutoModel(codigo="PROD-001", descricao="Chapa de Aço Inox 304 2mm"),
            ProdutoModel(codigo="PROD-002", descricao="Tubo Industrial Galvanizado 1/2"),
            ProdutoModel(codigo="PROD-003", descricao="Parafuso Sextavado M8 Zincado"),
            ProdutoModel(codigo="PROD-004", descricao="Eixo Maciço de Alumínio 20mm"),
            ProdutoModel(codigo="PROD-005", descricao="Resina Epóxi de Alta Viscosidade")
        ]
        session.add_all(produtos_padrao)
        session.commit()
    session.close()

popular_produtos_se_vazio()

# --- USUÁRIOS E SEGURANÇA (SHA-256) ---
USUARIOS = {
    "operador": {"senha": hashlib.sha256("senha123".encode()).hexdigest(), "perfil": "Operador"},
    "gerente": {"senha": hashlib.sha256("senha123".encode()).hexdigest(), "perfil": "Gerente"},
    "auditor": {"senha": hashlib.sha256("senha123".encode()).hexdigest(), "perfil": "Auditor"}
}

def autenticar(usuario, senha):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    if usuario in USUARIOS and USUARIOS[usuario]["senha"] == senha_hash:
        return USUARIOS[usuario]["perfil"]
    return None

def verificar_reincidencia_e_gerar_ap(session, processo, causa_raiz):
    count = session.query(NaoConformidadeModel).filter(
        NaoConformidadeModel.processo_origem == processo,
        NaoConformidadeModel.causa_raiz_definida == causa_raiz,
        NaoConformidadeModel.status == "Concluído"
    ).count()
    
    if count >= 3:
        id_ap_count = session.query(AcoesPreventivasModel).count()
        id_ap = f"AP-{datetime.now().strftime('%Y')}-{(id_ap_count + 1):04d}"
        
        ap_existente = session.query(AcoesPreventivasModel).filter_by(processo=processo, causa_raiz_gatilho=causa_raiz).first()
        if not ap_existente:
            nova_ap = AcoesPreventivasModel(
                id_ap=id_ap,
                processo=processo,
                causa_raiz_gatilho=causa_raiz,
                descricao_plano=f"Plano de Ação Corretiva/Preventiva Global gerado automaticamente devido a {count} reincidências de falhas no setor."
            )
            session.add(nova_ap)
            session.commit()
            return id_ap
    return None

# --- INTERFACE WEB STREAMLIT ---
st.set_page_config(page_title="SGQ ISO 9001", layout="wide")

if "perfil" not in st.session_state:
    st.session_state["perfil"] = None
    st.session_state["usuario"] = None

if st.session_state["perfil"] is None:
    st.title("🔐 Sistema de Gestão da Qualidade - Login")
    user_input = st.text_input("Usuário")
    pass_input = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        perfil = autenticar(user_input, pass_input)
        if perfil:
            st.session_state["perfil"] = perfil
            st.session_state["usuario"] = user_input
            st.rerun()
        else:
            st.error("Credenciais inválidas.")
else:
    st.sidebar.title(f"👤 {st.session_state['usuario'].upper()}")
    st.sidebar.write(f"Perfil: **{st.session_state['perfil']}**")
    menu = st.sidebar.radio("Navegação", ["Dashboard", "Registrar Saída NC", "Tratativa & Evidências", "Causa Raiz & Fechamento", "Planos Preventivos", "Auditoria de Dados"])
    
    if st.sidebar.button("Sair"):
        st.session_state["perfil"] = None
        st.session_state["usuario"] = None
        st.rerun()

    session = Session()

    # --- MÓDULO 1: DASHBOARD ---
    if menu == "Dashboard":
        st.title("📊 Painel de Controle de Saídas Não Conformes")
        ncs = session.query(NaoConformidadeModel).all()
        df = pd.DataFrame([nc.__dict__ for nc in ncs]) if ncs else pd.DataFrame()
        
        if not df.empty:
            df['atrasada'] = df.apply(lambda r: r['status'] != "Concluído" and datetime.utcnow() > r['prazo_sla'], axis=1)
            total_ncs = len(df)
            atrasadas = df['atrasada'].sum()
            aps_ativas = session.query(AcoesPreventivasModel).count()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Não Conformidades", total_ncs)
            c2.metric("Ocorrências com SLA Atrasado", atrasadas, delta_color="inverse")
            c3.metric("Planos Preventivos Globais", aps_ativas)
            
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            sns.set_theme(style="whitegrid")
            df['processo_origem'].value_counts().plot(kind='pie', ax=axes[0], autopct='%1.1f%%', colors=sns.color_palette("Blues_r"))
            axes[0].set_title("Ocorrências por Setor")
            axes[0].set_ylabel("")
            
            sns.countplot(data=df, x='impacto_potencial', hue='status', ax=axes[1], palette="Set2")
            axes[1].set_title("Status por Severidade de Impacto")
            st.pyplot(fig)
        else:
            st.info("Nenhuma ocorrência registrada para gerar gráficos estruturados.")

    # --- MÓDULO 2: CADASTRO COM OS NOVOS CAMPOS SOLICITADOS ---
    elif menu == "Registrar Saída NC":
        st.title("📝 Nova Saída Não Conforme (Cláusula 8.7.1)")
        
        # Carrega a lista de códigos de produtos existentes do banco (Planilha simulada)
        lista_produtos = session.query(ProdutoModel).all()
        dict_produtos = {p.codigo: p.descricao for p in lista_produtos}
        
        st.subheader("Rastreabilidade do Item Afetado")
        col1, col2 = st.columns(2)
        with col1:
            cod_prod = st.selectbox("Código do Produto (Vindo do Banco/Planilha)", list(dict_produtos.keys()))
            desc_prod = st.text_input("Descrição do Produto (Alimentada Automaticamente)", value=dict_produtos[cod_prod], disabled=True)
            num_nf = st.text_input("Número da Nota Fiscal (NF)")
        with col2:
            qtd_lote = st.number_input("Quantidade Total do Lote", min_value=0.0, step=1.0)
            qtd_rep = st.number_input("Quantidade Reprovada / Não Conforme", min_value=0.0, step=1.0)

        st.subheader("Dados da Ocorrência")
        desc = st.text_area("Descrição detalhada do desvio ou defeito encontrado")
        processo = st.selectbox("Processo / Setor de Origem", ["Produção", "Logística", "Engenharia", "Suprimentos", "Qualidade"])
        impacto = st.selectbox("Impacto Potencial de Risco", ["Baixo", "Médio", "Alto"])
        
        if st.button("Salvar Registro"):
            if not desc:
                st.error("Por favor, preencha a descrição do desvio.")
            elif not num_nf:
                st.error("Por favor, informe o número da Nota Fiscal.")
            elif qtd_rep > qtd_lote:
                st.error("Erro: A quantidade reprovada não pode ser maior que a quantidade total do lote.")
            elif qtd_rep <= 0:
                st.error("Por favor, preencha a quantidade reprovada.")
            else:
                id_count = session.query(NaoConformidadeModel).count()
                id_nc = f"NC-{datetime.now().strftime('%Y')}-{(id_count + 1):04d}"
                
                nova_nc = NaoConformidadeModel(
                    id_nc=id_nc,
