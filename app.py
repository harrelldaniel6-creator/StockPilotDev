import streamlit as st
import pandas as pd

st.set_page_config(page_title="Small Business Data Analyzer", layout="wide")

st.title("📊 Small Business Data Analyzer")

st.markdown("Upload your CSV file below to get started with analysis of sales, inventory, and labor data.")

uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.success("File uploaded successfully! Ready for analysis.")
    st.dataframe(df.head()) # Display the first few rows