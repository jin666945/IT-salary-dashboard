# ============================================================
# IT Talent Skill Gap & Salary Visualization Dashboard
# A Streamlit-based IT salary analysis web dashboard
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import numpy as np
from collections import Counter
from io import BytesIO

# ============================================================
# Load default data (500 software engineer job postings scraped from Indeed.com)
# ============================================================
@st.cache_data
def loadDefault():
    # File format is .xls but actually CSV, so use read_csv to read
    df = pd.read_csv('us_software_jobs_500.xls')
    # Calculate average salary (average of min and max)
    df['salary_avg'] = (df['min_amount'] + df['max_amount']) / 2
    # Filter out abnormal salary data (below 30k or above 350k)
    df_clean = df[(df['salary_avg'] >= 30000) & (df['salary_avg'] <= 350000)].copy()
    return df_clean

# ============================================================
# Extract state name from location field
# 从location字段提取州名（State）
# ============================================================
def getState(location):
    # Handle null/empty values
    if pd.isna(location) or str(location).strip() == '':
        return 'Other'
    text = str(location).strip()
    if ',' in text:
        # If comma exists, format might be 'City, State'
        # 如果有逗号，说明格式可能是 "City, State"
        parts = [p.strip() for p in text.split(',') if p.strip()]
        for part in parts:
            # Try to find 2-letter uppercase state code (e.g. CA, NY, TX)
            # 尝试找到两位大写字母组成的州代码（如 CA, NY, TX）
            if len(part) == 2 and part.isupper() and part.isalpha():
                return part
        # If no state code found, return the last part
        # 如果没找到州代码，返回最后一部分
        return parts[-1] if parts else 'Other'
    # If no comma, split by space
    # 如果没有逗号，按空格分割
    parts = text.split()
    for part in parts:
        if len(part) == 2 and part.isupper() and part.isalpha():
            return part
    return text if text else 'Other'

# ============================================================
# Extract education level from description text
# 从描述文本中提取学历信息
# ============================================================
def getEducation(text):
    if pd.isna(text):
        return 'Not Specified'
    text = str(text).lower()
    if 'phd' in text or 'doctorate' in text:
        return 'PhD'
    elif 'master' in text or 'm.s.' in text or 'm.a.' in text:
        return 'Master'
    elif 'bachelor' in text or 'b.s.' in text or 'b.a.' in text or re.search(r'\bbs\b', text):
        return 'Bachelor'
    elif 'associate' in text:
        return 'Associate'
    else:
        return 'Not Specified'

# ============================================================
# Skill keyword list
# ============================================================
skillList = [
    'Python', 'Java', 'JavaScript', 'C++', 'C#', 'Go', 'Ruby', 'Rust',
    'SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis',
    'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins',
    'React', 'Angular', 'Vue', 'Node.js', 'Spring', 'Django', 'Flask', 'FastAPI',
    'Hadoop', 'Spark', 'Kafka', 'TensorFlow', 'PyTorch', 'Pandas', 'NumPy',
    'Linux', 'Git', 'DevOps', 'Microservices', 'REST', 'GraphQL',
    'Machine Learning', 'AI', 'Data Science', 'Cloud', 'Security',
    'Elasticsearch', 'RabbitMQ', 'Terraform', 'Ansible', 'Prometheus',
    'Kibana', 'Elastic Stack', 'Power BI', 'Tableau', 'Excel'
]

# ============================================================
# Extract skill list from data row
# 从数据行中提取技能列表
# Prefer skills column, fallback to scanning description for keywords
# 优先使用skills列，如果没有则从description中扫描关键词
# ============================================================
def getSkills(row):
    # First check if there's a separate skills column
    # 先检查是否有独立的skills列
    skills_val = row.get('skills', pd.NA)
    if pd.notna(skills_val) and str(skills_val).strip() not in ('', 'None', 'nan'):
        # If skills column exists, split by comma
        # 如果有skills列，按逗号分割
        return [s.strip() for s in str(skills_val).split(',') if s.strip()]
    # If no skills column, scan from description
    # 如果没有skills列，从description中扫描
    if pd.isna(row.get(st.session_state.descCol, pd.NA)):
        return []
    text = str(row[st.session_state.descCol]).lower()
    found = []
    for skill in skillList:
        # 将 if skill.lower() in text: 替换为：
        if re.search(r'\b' + re.escape(skill.lower()) + r'\b', text):
            found.append(skill)
    return found

# ============================================================
# Extract years of experience from description text
# 从描述文本中提取工作经验年限
# ============================================================
def getExperience(desc):
    if pd.isna(desc):
        return np.nan
    text = str(desc)
    # Match patterns like '3 years', '5+ years', '2 yrs', '3 years+' etc.
    # 匹配 "3 years", "5+ years", "2 yrs", "3 years+" 等格式
    match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)\+?', text, re.IGNORECASE)
    if match:
        val = int(match.group(1))
        # Filter out unreasonable values (e.g. 'year 2000' misidentified as 2000 years)
        # 过滤掉不合理的数据（比如把 "year 2000" 误识别为2000年经验）
        if 0 < val <= 30:
            return val
    return np.nan

# ============================================================
# Session state — 跨页面刷新保存上传的数据
# ============================================================
if 'useUpload' not in st.session_state:
    st.session_state.useUpload = False
    st.session_state.uploadDf = None
    st.session_state.tempDf = None
    st.session_state.salCol = 'salary_avg'
    st.session_state.locCol = 'location'
    st.session_state.descCol = 'description'
if 'defaultDf' not in st.session_state:
    st.session_state.defaultDf = loadDefault()

# ============================================================
# Page configuration
# ============================================================
st.set_page_config(page_title="IT Salary Dashboard", layout="wide")
# ---- 全局 CSS 微调（让页面更舒服） ----
st.markdown("""
<style>
/* 让数字卡片更圆润 */
[data-testid="metric-container"] {
    background: #f8fafc;
    border-radius: 16px;
    padding: 15px 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    border: 1px solid #f1f5f9;
}
/* 调整侧边栏字体 */
.css-1d391kg {
    font-weight: 500;
}
/* 让分割线变淡 */
hr {
    opacity: 0.3;
}
/* 调整标题间距 */
h1, h2, h3 {
    letter-spacing: -0.3px;
}
</style>
""", unsafe_allow_html=True)
st.title("IT Talent Skill Gap & Salary Visualization")

# ============================================================
# Welcome popup — shown on first page load
# ============================================================
if 'showWelcome' not in st.session_state:
    st.session_state.showWelcome = True

if st.session_state.showWelcome:
    # ---- 注入自定义 CSS 美化 ----
    st.markdown("""
    <style>
    .glass-card {
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 24px;
        padding: 40px 40px 30px 40px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.08), 0 8px 20px rgba(0, 0, 0, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.8);
        text-align: center;
        max-width: 800px;
        margin: 20px auto;
        transition: all 0.3s ease;
    }
    .gradient-text {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 10px;
    }
    .feature-badge {
        display: inline-block;
        background: #f0f4ff;
        padding: 6px 16px;
        border-radius: 30px;
        font-size: 0.85rem;
        font-weight: 500;
        color: #4a5568;
        margin: 4px 6px;
        border: 1px solid #e2e8f0;
    }
    .get-started-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 12px 48px !important;
        border-radius: 40px !important;
        border: none !important;
        font-size: 1.1rem !important;
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.35) !important;
        transition: transform 0.2s ease !important;
        margin-top: 15px;
    }
    .get-started-btn:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 12px 28px rgba(102, 126, 234, 0.5) !important;
    }
    .sub-text {
        color: #718096;
        font-size: 0.95rem;
        margin-top: 15px;
        border-top: 1px solid #e2e8f0;
        padding-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

    # ---- 弹窗主体 ----
    st.markdown("""
    <div class="glass-card">
        <div style="font-size: 3rem; margin-bottom: 0;">🚀</div>
        <div class="gradient-text">IT Talent Skill Gap & Salary Dashboard</div>
        <p style="font-size: 1.15rem; color: #4a5568; margin: 10px 0 20px 0; font-weight: 400;">
            Explore IT job market data · Identify skill gaps · Make data-driven decisions
        </p>
        <div style="margin: 20px 0;">
            <span class="feature-badge">📊 Salary Distribution</span>
            <span class="feature-badge">🗺️ State Comparison</span>
            <span class="feature-badge">🛠️ Skill Demand</span>
            <span class="feature-badge">🎓 Education Impact</span>
            <span class="feature-badge">📁 Upload Custom Data</span>
            <span class="feature-badge">📥 Export Results</span>
        </div>
        <div class="sub-text">
            Built with Python · Streamlit · Plotly · Pandas
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---- Get Started 按钮 ----
    if st.button("✨ Get Started", key="closeWelcome", use_container_width=False):
        st.session_state.showWelcome = False
        st.rerun()

    st.stop()

# ============================================================
# Sidebar: Upload custom data
# 侧边栏：上传自定义数据
# ============================================================
st.sidebar.divider()
st.sidebar.subheader("Upload Your Own Data")
uploadFile = st.sidebar.file_uploader(
    "Upload CSV or Excel file",
    type=['csv', 'xlsx'],
    help="Upload your own recruitment data and the system will analyze it automatically"
)

if uploadFile is not None:
    try:
        if uploadFile.name.endswith('.csv'):
            tempDf = pd.read_csv(uploadFile)
        else:
            tempDf = pd.read_excel(uploadFile)

        tempDf = tempDf.drop_duplicates()
        st.sidebar.info(f"Loaded {len(tempDf)} rows, {len(tempDf.columns)} columns")

        # Smart column detection + manual user selection
        # 智能列检测 + 用户手动选择
        st.sidebar.markdown("### Please specify data columns")

        all_cols = list(tempDf.columns)
        numeric_cols = list(tempDf.select_dtypes(include=['number']).columns)

        # Step 1: Salary column
        # Step 1: 薪资列
        min_candidates = [c for c in all_cols if 'min' in c.lower() and ('salary' in c.lower() or 'amount' in c.lower())]
        max_candidates = [c for c in all_cols if 'max' in c.lower() and ('salary' in c.lower() or 'amount' in c.lower())]

        if min_candidates and max_candidates:
            st.sidebar.info("Detected both min and max salary columns.")
            use_avg = st.sidebar.radio(
                "Salary source",
                ["Calculate average from min + max", "Use a single column directly"],
                index=0
            )
            if use_avg == "Calculate average from min + max":
                min_col = st.sidebar.selectbox("Min salary column", min_candidates, index=0)
                max_col = st.sidebar.selectbox("Max salary column", max_candidates, index=0)
                try:
                    min_vals = pd.to_numeric(tempDf[min_col], errors='coerce')
                    max_vals = pd.to_numeric(tempDf[max_col], errors='coerce')
                    tempDf['salary_avg'] = (min_vals + max_vals) / 2
                    st.sidebar.success(f"Calculated average from '{min_col}' and '{max_col}'")
                except:
                    st.sidebar.error("Could not calculate average. Please check the columns.")
                    st.stop()
            else:
                if numeric_cols and numeric_cols[0] in all_cols:
                    default_idx = all_cols.index(numeric_cols[0])
                else:
                    default_idx = 0
                salCol = st.sidebar.selectbox("Select salary column", all_cols, index=default_idx)
                try:
                    tempDf['salary_avg'] = pd.to_numeric(tempDf[salCol], errors='coerce')
                    st.sidebar.success(f"Using '{salCol}' as salary")
                except:
                    st.sidebar.error("Could not convert to numeric. Please choose a different column.")
                    st.stop()
        else:
            if numeric_cols and numeric_cols[0] in all_cols:
                default_idx = all_cols.index(numeric_cols[0])
            else:
                default_idx = 0
            salCol = st.sidebar.selectbox("Select the column containing salary", all_cols, index=default_idx)
            try:
                tempDf['salary_avg'] = pd.to_numeric(tempDf[salCol], errors='coerce')
                st.sidebar.success(f"Using '{salCol}' as salary")
            except:
                st.sidebar.error("Could not convert to numeric. Please choose a different column.")
                st.stop()

        # Step 2: Location column
        # Step 2: 位置列
        loc_candidates = [c for c in all_cols if 'location' in c.lower() or 'city' in c.lower() or 'state' in c.lower()]
        if loc_candidates:
            locCol = st.sidebar.selectbox("Select the column containing location", loc_candidates, index=0)
        else:
            locCol = st.sidebar.selectbox("Select the column containing location", all_cols, index=0)
        tempDf['location'] = tempDf[locCol]

        # Step 3: Description column
        # Step 3: 描述列
        desc_candidates = [c for c in all_cols if 'description' in c.lower() or 'desc' in c.lower()]
        if desc_candidates:
            descCol = st.sidebar.selectbox("Select the column containing job description", desc_candidates, index=0)
        else:
            descCol = st.sidebar.selectbox("Select the column containing job description", all_cols, index=min(1, len(all_cols)-1))
        tempDf['description'] = tempDf[descCol]

        # ---- Data Quality Check ----
        # ---- 数据质量检查 ----
        st.sidebar.markdown("---")
        st.sidebar.subheader("Data Quality Check")

        totalRows = len(tempDf)
        nullCounts = tempDf.isnull().sum()
        highNullCols = nullCounts[nullCounts > totalRows * 0.5]

        if len(highNullCols) > 0:
            st.sidebar.warning(f"{len(highNullCols)} columns have >50% missing values:")
            for col in highNullCols.index:
                pct = nullCounts[col] / totalRows * 100
                st.sidebar.caption(f"  - {col}: {pct:.1f}% missing")
        else:
            st.sidebar.success("No columns with excessive missing data")

        st.sidebar.caption(f"Total rows: {totalRows}")
        st.sidebar.caption(f"Null values: {nullCounts.sum()}")
        st.sidebar.caption(f"Duplicate rows removed: {tempDf.duplicated().sum()}")

        st.sidebar.success("Column mapping complete!")
        st.session_state.salCol = 'salary_avg'
        st.session_state.locCol = 'location'
        st.session_state.descCol = 'description'

        st.sidebar.info(f"Loaded {len(tempDf)} rows, {len(tempDf.columns)} columns")

        st.session_state.tempDf = tempDf.copy()

        if st.sidebar.button("Apply Uploaded Data", type="primary"):
            st.session_state.uploadDf = st.session_state.tempDf.copy()
            st.session_state.useUpload = True
            st.rerun()

    except Exception as e:
        st.sidebar.error(f"Failed to read file: {e}")

# ============================================================
# Reset button — go back to default data
# ============================================================
if st.session_state.useUpload:
    if st.sidebar.button("Reset to Default Data"):
        st.session_state.useUpload = False
        st.session_state.uploadDf = None
        st.session_state.tempDf = None
        st.rerun()

# ============================================================
# Choose which dataset to use (default or uploaded)
# 选择使用哪份数据（默认或上传的）
# ============================================================
if st.session_state.useUpload and st.session_state.uploadDf is not None:
    df = st.session_state.uploadDf.copy()
    st.info(f"Using uploaded data: {len(df)} records")
else:
    df = st.session_state.defaultDf.copy()
    st.session_state.useUpload = False

# ============================================================
# Dynamic subtitle — changes based on data source
# 动态副标题 — 根据数据来源变化
# ============================================================
if st.session_state.useUpload:
    st.markdown("Analysis based on uploaded data")
else:
    st.markdown("Analysis based on 500 software engineer job postings from Indeed.com")

# ============================================================
# Sidebar: Data filtering
# 侧边栏：数据过滤
# ============================================================
st.sidebar.divider()
st.sidebar.header("Filter Data")

minSal = int(df[st.session_state.salCol].min())
maxSal = int(df[st.session_state.salCol].max())
salRange = st.sidebar.slider(
    "Select Salary Range (USD)",
    min_value=minSal,
    max_value=maxSal,
    value=(minSal, maxSal),
    step=5000
)

binCount = st.sidebar.slider(
    "Number of Histogram Bins",
    min_value=5,
    max_value=50,
    value=25,
    step=1
)

filteredDf = df[(df[st.session_state.salCol] >= salRange[0]) & (df[st.session_state.salCol] <= salRange[1])]
st.sidebar.write(f"Jobs after filtering: **{len(filteredDf)}**")

# ---- Job/Keyword Search (终极修复版) ----
st.sidebar.divider()
st.sidebar.header("Search Jobs")

jobSearch = st.sidebar.text_input(
    "Search by job title or keyword",
    placeholder="e.g. Python, Java, engineer...",
    help="Searches across Title, Skills, and Description"
)

if jobSearch:
    search_lower = jobSearch.lower()
    
    # 【修复】不再写死列名，而是动态获取当前数据里存在的文本列
    search_columns = []
    # 如果存在标题列
    if 'title' in filteredDf.columns:
        search_columns.append('title')
    # 描述列（你在侧边栏映射好的）
    if st.session_state.descCol in filteredDf.columns:
        search_columns.append(st.session_state.descCol)
    # 技能列（如果有）
    if 'skills' in filteredDf.columns:
        search_columns.append('skills')
    if 'skills_found' in filteredDf.columns:
        search_columns.append('skills_found')
    
    # 如果上面都没找到，就用所有文本列作为备选
    if not search_columns:
        search_columns = filteredDf.select_dtypes(include=['object']).columns.tolist()
    
    mask = pd.Series([False] * len(filteredDf), index=filteredDf.index)
    found_in_cols = []
    
    for col in search_columns:
        if col in filteredDf.columns:
            col_data = filteredDf[col].astype(str).fillna("").str.lower()
            match = col_data.str.contains(search_lower, na=False)
            mask = mask | match
            if match.any():
                found_in_cols.append(col)
    
    filteredDf = filteredDf[mask]
    
    if len(filteredDf) > 0:
        st.sidebar.success(f"Found {len(filteredDf)} jobs matching '{jobSearch}'")
        if found_in_cols:
            st.sidebar.caption(f"Matches found in: {', '.join(found_in_cols)}")
    else:
        st.sidebar.warning(f"No matches for '{jobSearch}'. Try checking spelling.")

# ============================================================
# Sidebar: Download data
# ============================================================
st.sidebar.divider()
st.sidebar.subheader("Download Data")

def to_excel_download(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Filtered Data', index=False)
        # Auto-adjust column width
        # 自动调整列宽
        worksheet = writer.sheets['Filtered Data']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    return output.getvalue()

excel_data = to_excel_download(filteredDf)
st.sidebar.download_button(
    label="Download Filtered Data (Excel)",
    data=excel_data,
    file_name="filtered_jobs_data.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ---- Export as CSV ----
# ---- 导出为CSV（新增功能） ----
csv_data = filteredDf.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="Download Filtered Data (CSV)",
    data=csv_data,
    file_name="filtered_jobs_data.csv",
    mime="text/csv"
)

if st.session_state.useUpload:
    st.sidebar.caption("Data source: Uploaded file")
else:
    st.sidebar.caption("Data source: Indeed.com (default)")

# ---- About button ----
# ---- About 按钮（新增功能） ----
if st.sidebar.button("About"):
    st.session_state.showAbout = True

if st.session_state.get('showAbout', False):
    st.divider()
    st.subheader("About This Project")
    st.markdown("""
    **IT Talent Skill Gap & Salary Visualization** is a web-based dashboard
    designed to help job seekers and HR professionals analyze the IT job market.

    **Features:**
    - Salary distribution analysis with interactive histograms
    - State-by-state salary comparison
    - Most in-demand skills identification
    - Experience and education impact on salary
    - Skills demand heatmap by state
    - Salary impact analysis of individual skills
    - Custom data upload and filtering
    - Data export in Excel and CSV formats

    **Tech Stack:**
    - Python 3
    - Streamlit (web framework)
    - Plotly (interactive charts)
    - Pandas (data processing)

    **Data Source:**
    - Default dataset: 500 software engineer job postings from Indeed.com
    """)
    if st.button("Back to Dashboard"):
        st.session_state.showAbout = False
        st.rerun()

# ============================================================
# KPI cards
# KPI 卡片
# ============================================================
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Jobs", len(filteredDf))
col2.metric("Average Salary", f"${filteredDf[st.session_state.salCol].mean():,.0f}")
col3.metric("Highest Salary", f"${filteredDf[st.session_state.salCol].max():,.0f}")
col4.metric("Lowest Salary", f"${filteredDf[st.session_state.salCol].min():,.0f}")
col5.metric("Median Salary", f"${filteredDf[st.session_state.salCol].median():,.0f}")

# ---- Salary percentile indicator ----
# ---- 薪资分位数提示（新增功能） ----
p90 = filteredDf[st.session_state.salCol].quantile(0.9)
st.caption(f"Top 10% salary threshold: ${p90:,.0f}")

st.divider()

# ============================================================
# Ensure required columns exist (state, education, skills_found)
# 确保必要的列存在（state, education, skills_found）
# ============================================================
if 'state' not in filteredDf.columns:
    filteredDf['state'] = filteredDf[st.session_state.locCol].apply(getState)
if 'education' not in filteredDf.columns:
    filteredDf['education'] = filteredDf[st.session_state.descCol].apply(getEducation)
# skills_found: only compute once if not exists, to avoid redundant calculation
# skills_found 只在不存在时计算一次，避免重复计算
if 'skills_found' not in filteredDf.columns:
    filteredDf['skills_found'] = filteredDf.apply(getSkills, axis=1)

# ============================================================
# Chart 1: Salary distribution
# Chart 1: 薪资分布
# ============================================================
st.subheader("Salary Distribution")
figHist = px.histogram(
    filteredDf,
    x=st.session_state.salCol,
    nbins=binCount,
    title=f'Distribution of Annual Salaries for IT Jobs (bins = {binCount})',
    labels={st.session_state.salCol: 'Annual Salary (USD)', 'count': 'Number of Jobs'},
    color_discrete_sequence=['steelblue'],
    opacity=0.8
)
figHist.update_layout(
    xaxis_title='Annual Salary (USD)',
    yaxis_title='Number of Jobs',
    hovermode='x',
    bargap=0.05
)
figHist.update_traces(hovertemplate='Salary: $%{x:,.0f}<br>Count: %{y}')
st.plotly_chart(figHist, use_container_width=True)

# Auto-generated analysis conclusion
# 自动分析结论
avg_sal = filteredDf[st.session_state.salCol].mean()
median_sal = filteredDf[st.session_state.salCol].median()
max_sal = filteredDf[st.session_state.salCol].max()
min_sal = filteredDf[st.session_state.salCol].min()

st.info(f"""
What this chart tells you:
- Most salaries are concentrated between \${median_sal:,.0f} and \${avg_sal:,.0f}.
- The highest salary in this dataset is \${max_sal:,.0f}, while the lowest is \${min_sal:,.0f}.
- The distribution shows a right-skewed pattern, meaning a small number of high-paying jobs pull the average up.
""")

with st.expander("View salary distribution data"):
    st.dataframe(filteredDf[[st.session_state.salCol]].describe(), use_container_width=True)

# ============================================================
# Chart 2: Average salary by state
# Chart 2: 各州平均薪资
# ============================================================
st.subheader("Average Salary by State")

stateStats = filteredDf.groupby('state').agg(
    avg_salary=(st.session_state.salCol, 'mean'),
    job_count=(st.session_state.salCol, 'count')
).sort_values('avg_salary', ascending=False).reset_index()

topStates = stateStats.head(10)

sortOrder = st.radio("Sort Order", ["Descending (High to Low)", "Ascending (Low to High)"], horizontal=True, index=0)
ascFlag = (sortOrder == "Ascending (Low to High)")
topStatesSorted = topStates.sort_values('avg_salary', ascending=ascFlag)

figState = px.bar(
    topStatesSorted,
    x='state',
    y='avg_salary',
    text='avg_salary',
    title='Average IT Salary by State (Top 10)',
    labels={'state': 'State', 'avg_salary': 'Average Salary (USD)'},
    color='avg_salary',
    color_continuous_scale='Blues',
    hover_data={'job_count': True}
)
figState.update_traces(
    texttemplate='$%{text:,.0f}',
    textposition='outside',
    hovertemplate='State: %{x}<br>Avg Salary: $%{y:,.0f}<br>Jobs: %{customdata[0]}<extra></extra>'
)
figState.update_layout(
    xaxis_title='State',
    yaxis_title='Average Salary (USD)',
    uniformtext_minsize=8,
    uniformtext_mode='hide'
)
st.plotly_chart(figState, use_container_width=True)

top_state = topStates.iloc[0]['state'] if len(topStates) > 0 else "N/A"
top_salary = topStates.iloc[0]['avg_salary'] if len(topStates) > 0 else 0
bottom_state = topStates.iloc[-1]['state'] if len(topStates) > 0 else "N/A"
bottom_salary = topStates.iloc[-1]['avg_salary'] if len(topStates) > 0 else 0

st.info(f"""
What this chart tells you:
- {top_state} has the highest average salary at ${top_salary:,.0f}, which is {((top_salary - bottom_salary) / bottom_salary * 100):.0f}% higher than the lowest-paying state ({bottom_state}).
- Geographic location plays a significant role in IT compensation.
""")

with st.expander("View state salary data"):
    st.dataframe(topStates, use_container_width=True)

# ============================================================
# Compare Analysis — comparison module
# Compare Analysis — 对比分析模块
# ============================================================
st.subheader("Compare Analysis")

# Collect all skills using a more efficient method
# 用更高效的方式收集所有技能
allSkills = sorted(set().union(*filteredDf['skills_found'].tolist()))

compType = st.selectbox(
    "Compare by",
    ["States", "Skills", "Education"],
    index=0
)

if compType == "States":
    statesList = sorted(filteredDf[filteredDf['state'] != 'Unknown']['state'].unique())

    if len(statesList) >= 2:
        col1, col2 = st.columns(2)
        with col1:
            stateA = st.selectbox("State A", statesList, index=0)
        with col2:
            stateB = st.selectbox("State B", statesList, index=min(1, len(statesList)-1))

        dataA = filteredDf[filteredDf['state'] == stateA]
        dataB = filteredDf[filteredDf['state'] == stateB]

        if len(dataA) > 0 and len(dataB) > 0:
            colX, colY, colZ = st.columns(3)
            colX.metric(f"{stateA} Jobs", len(dataA))
            colY.metric(f"{stateB} Jobs", len(dataB))
            diffSal = dataA[st.session_state.salCol].mean() - dataB[st.session_state.salCol].mean()
            colZ.metric("Diff", f"${diffSal:,.0f}", delta=f"{'higher' if diffSal > 0 else 'lower'} than {stateB}")

            figCmp = go.Figure()
            figCmp.add_trace(go.Bar(
                x=[stateA, stateB],
                y=[dataA[st.session_state.salCol].mean(), dataB[st.session_state.salCol].mean()],
                text=[f"${dataA[st.session_state.salCol].mean():,.0f}", f"${dataB[st.session_state.salCol].mean():,.0f}"],
                textposition='outside',
                marker_color=['steelblue', 'coral']
            ))
            figCmp.update_layout(
                title=f"{stateA} vs {stateB} — Avg Salary",
                yaxis_title="Avg Salary (USD)",
                height=400
            )
            st.plotly_chart(figCmp, use_container_width=True)
            
            # ===== T-test for States comparison  =====  # 针对州的T检验
            from scipy import stats
            vals_a = dataA[st.session_state.salCol].dropna()
            vals_b = dataB[st.session_state.salCol].dropna()
            if len(vals_a) > 1 and len(vals_b) > 1:
                t_stat, p_val = stats.ttest_ind(vals_a, vals_b)
                if p_val < 0.05:
                    # Significant difference  # 差异显著
                    st.success(f"📊 Statistical Conclusion: The salary difference is significant (p = {p_val:.4f} < 0.05), indicating a reliable difference.")
                else:
                    # Not significant  # 差异不显著
                    st.warning(f"📊 Statistical Conclusion: The salary difference is NOT significant (p = {p_val:.4f} > 0.05), possibly due to sampling error.")
            else:
                # Too few samples  # 样本太少
                st.info("Insufficient sample data (less than 2 observations) for T-test.")
        else:
            st.info("Not enough data for selected states — try others")
    else:
        st.info("Need at least 2 states with data")

elif compType == "Skills":
    if len(allSkills) >= 2:
        col1, col2 = st.columns(2)
        with col1:
            skillA = st.selectbox("Skill A", allSkills, index=0)
        with col2:
            skillB = st.selectbox("Skill B", allSkills, index=min(1, len(allSkills)-1))

        dataA = filteredDf[filteredDf['skills_found'].apply(lambda x: skillA in x)]
        dataB = filteredDf[filteredDf['skills_found'].apply(lambda x: skillB in x)]

        if len(dataA) > 0 and len(dataB) > 0:
            colX, colY, colZ = st.columns(3)
            colX.metric(f"{skillA} Jobs", len(dataA))
            colY.metric(f"{skillB} Jobs", len(dataB))
            diffSal = dataA[st.session_state.salCol].mean() - dataB[st.session_state.salCol].mean()
            colZ.metric("Diff", f"${diffSal:,.0f}", delta=f"{'higher' if diffSal > 0 else 'lower'} than {skillB}")

            figCmp = go.Figure()
            figCmp.add_trace(go.Bar(
                x=[skillA, skillB],
                y=[dataA[st.session_state.salCol].mean(), dataB[st.session_state.salCol].mean()],
                text=[f"${dataA[st.session_state.salCol].mean():,.0f}", f"${dataB[st.session_state.salCol].mean():,.0f}"],
                textposition='outside',
                marker_color=['steelblue', 'coral']
            ))
            figCmp.update_layout(
                title=f"{skillA} vs {skillB} — Avg Salary",
                yaxis_title="Avg Salary (USD)",
                height=400
            )
            st.plotly_chart(figCmp, use_container_width=True)
            
            # ===== T-test for Skills comparison  =====  # 针对技能的T检验
            from scipy import stats
            vals_a = dataA[st.session_state.salCol].dropna()
            vals_b = dataB[st.session_state.salCol].dropna()
            if len(vals_a) > 1 and len(vals_b) > 1:
                t_stat, p_val = stats.ttest_ind(vals_a, vals_b)
                if p_val < 0.05:
                    # Significant difference  # 差异显著
                    st.success(f"📊 Statistical Conclusion: The salary difference is significant (p = {p_val:.4f} < 0.05), indicating a reliable difference.")
                else:
                    # Not significant  # 差异不显著
                    st.warning(f"📊 Statistical Conclusion: The salary difference is NOT significant (p = {p_val:.4f} > 0.05), possibly due to sampling error.")
            else:
                # Too few samples  # 样本太少
                st.info("Insufficient sample data (less than 2 observations) for T-test.")
        else:
            st.info("Not enough data for selected skills — try others")
    else:
        st.info("Need at least 2 skills with data")

else:
    eduList = sorted(filteredDf['education'].unique())
    if len(eduList) >= 2:
        col1, col2 = st.columns(2)
        with col1:
            eduA = st.selectbox("Education A", eduList, index=0)
        with col2:
            eduB = st.selectbox("Education B", eduList, index=min(1, len(eduList)-1))

        dataA = filteredDf[filteredDf['education'] == eduA]
        dataB = filteredDf[filteredDf['education'] == eduB]

        if len(dataA) > 0 and len(dataB) > 0:
            colX, colY, colZ = st.columns(3)
            colX.metric(f"{eduA} Jobs", len(dataA))
            colY.metric(f"{eduB} Jobs", len(dataB))
            diffSal = dataA[st.session_state.salCol].mean() - dataB[st.session_state.salCol].mean()
            colZ.metric("Diff", f"${diffSal:,.0f}", delta=f"{'higher' if diffSal > 0 else 'lower'} than {eduB}")

            figCmp = go.Figure()
            figCmp.add_trace(go.Bar(
                x=[eduA, eduB],
                y=[dataA[st.session_state.salCol].mean(), dataB[st.session_state.salCol].mean()],
                text=[f"${dataA[st.session_state.salCol].mean():,.0f}", f"${dataB[st.session_state.salCol].mean():,.0f}"],
                textposition='outside',
                marker_color=['steelblue', 'coral']
            ))
            figCmp.update_layout(
                title=f"{eduA} vs {eduB} — Avg Salary",
                yaxis_title="Avg Salary (USD)",
                height=400
            )
            st.plotly_chart(figCmp, use_container_width=True)
            # 【新增】自动计算统计学显著性（T检验）
            from scipy import stats
            vals_a = dataA[st.session_state.salCol].dropna()
            vals_b = dataB[st.session_state.salCol].dropna()
            if len(vals_a) > 1 and len(vals_b) > 1:
                t_stat, p_val = stats.ttest_ind(vals_a, vals_b)
                if p_val < 0.05:
                    st.success(f"📊 Statistical Conclusion: The salary difference is significant (p = {p_val:.4f} < 0.05), indicating a reliable difference.")
                else:
                    st.warning(f"📊 Statistical Conclusion: The salary difference is NOT significant (p = {p_val:.4f} > 0.05), possibly due to sampling error.")
            else:
                st.info("Insufficient sample data (less than 2 observations) for T-test.")
        else:
            st.info("Not enough data for selected education levels")
    else:
        st.info("Need at least 2 education levels with data")

# ============================================================
# Chart 2.5: Skills Demand Heatmap by State
# 技能需求热力图（技能 x 各州的需求相关性）
# ============================================================
st.subheader("Skills Demand Heatmap by State")
# 按州展示技能需求热力图

if len(filteredDf) > 10 and 'skills_found' in filteredDf.columns:
    try:
        # compute skill counter locally for this chart
        # 在这个图表内部单独计算技能计数器，避免依赖后面才定义的变量
        from collections import Counter
        heatmapSkillCounter = Counter()
        for skills in filteredDf['skills_found']:
            heatmapSkillCounter.update(skills)
        
        top20Skills = [s for s, c in heatmapSkillCounter.most_common(20)]
        stateSkillData = pd.DataFrame(0, index=sorted(filteredDf['state'].unique()), columns=top20Skills)
        
        for idx, row in filteredDf.iterrows():
            for skill in row['skills_found']:
                if skill in top20Skills:
                    stateSkillData.loc[row['state'], skill] += 1
        
        # normalize to percentage
        # 归一化为百分比
        stateSkillPct = stateSkillData.div(stateSkillData.sum(axis=1), axis=0) * 100
        stateSkillPct = stateSkillPct.fillna(0)
        # remove rows with all zeros
        # 去掉全为0的行
        stateSkillPct = stateSkillPct[stateSkillPct.sum(axis=1) > 0]
        
        if len(stateSkillPct) > 1 and len(stateSkillPct.columns) > 1:
            import plotly.graph_objects as go
            figHeat = go.Figure(data=go.Heatmap(
                z=stateSkillPct.values,
                x=stateSkillPct.columns,
                y=stateSkillPct.index,
                colorscale='YlOrRd',
                text=stateSkillPct.values,
                texttemplate='%{text:.0f}%',
                textfont={"size": 9},
                hovertemplate='State: %{y}<br>Skill: %{x}<br>Job Share: %{z:.0f}%<extra></extra>'
            ))
            figHeat.update_layout(
                title='Skill Demand Share by State (Top 20 Skills)',
                xaxis_title='Skill',
                yaxis_title='State',
                height=550,
                width=1100
            )
            st.plotly_chart(figHeat, use_container_width=True)
            
            st.info("""
**What this chart tells you:**
- Darker colors mean more jobs requiring that skill in that state.
- You can spot regional skill preferences, e.g. California may favor "React" while Texas prefers "Java".
- Job seekers can pick a state and see which skills are most valued there.
""")
    except:
        st.info("Not enough data to display the heatmap. Try adjusting your filters.")

# ============================================================
# Chart 3: Most popular skills
# Chart 3: 最热门技能
# ============================================================
# Use Counter to count all skill occurrences
# 用Counter统计所有技能出现次数
allSkillsList = []
for skills in filteredDf['skills_found']:
    allSkillsList.extend(skills)
skillCounter = Counter(allSkillsList)

topN = st.selectbox("Show Top N Skills", [10, 15, 20], index=1)
st.subheader(f"Most In-Demand IT Skills (Top {topN})")
topSkills = skillCounter.most_common(topN)

skillsDf = pd.DataFrame(topSkills, columns=['Skill', 'Count'])
skillsDf['Percentage'] = (skillsDf['Count'] / len(filteredDf)) * 100

skillsDfTop = skillsDf.head(topN).sort_values('Percentage', ascending=True)

figSkills = px.bar(
    skillsDfTop,
    x='Percentage',
    y='Skill',
    orientation='h',
    title=f'Top {topN} Most Frequently Mentioned IT Skills in Job Postings',
    labels={'Percentage': 'Percentage of Job Postings (%)', 'Skill': ''},
    text='Percentage',
    color='Percentage',
    color_continuous_scale='Viridis'
)
figSkills.update_traces(
    texttemplate='%{text:.1f}%',
    textposition='outside',
    hovertemplate='Skill: %{y}<br>Percentage: %{x:.1f}%<br>Count: %{customdata[0]}<extra></extra>',
    customdata=skillsDfTop[['Count']].values
)
figSkills.update_layout(height=500, xaxis_range=[0, 105])
st.plotly_chart(figSkills, use_container_width=True)

top_skill = skillsDf.iloc[0]['Skill'] if len(skillsDf) > 0 else "N/A"
top_pct = skillsDf.iloc[0]['Percentage'] if len(skillsDf) > 0 else 0
second_skill = skillsDf.iloc[1]['Skill'] if len(skillsDf) > 1 else "N/A"
second_pct = skillsDf.iloc[1]['Percentage'] if len(skillsDf) > 1 else 0

st.info(f"""
What this chart tells you:
- {top_skill} is mentioned in {top_pct:.1f}% of all job postings — it's the most in-demand skill.
- {second_skill} follows at {second_pct:.1f}%, showing a clear skills hierarchy in the job market.
- If you're a job seeker, prioritize learning the top skills shown above.
""")

with st.expander("View skills demand data"):
    st.dataframe(skillsDf, use_container_width=True)

# ============================================================
# Chart 4: Experience vs salary
# Chart 4: 工作经验与薪资的关系
# ============================================================
st.subheader("Experience vs Salary")

filteredDf['experience_years'] = filteredDf[st.session_state.descCol].apply(getExperience)
expData = filteredDf[filteredDf['experience_years'].notna()]
# Filter out abnormal data with more than 30 years
# 过滤掉超过30年的异常数据
expData = expData[expData['experience_years'] <= 30]

if len(expData) > 5:
    expSalary = expData.groupby('experience_years')[st.session_state.salCol].mean().reset_index()
    figExp = px.line(
        expSalary,
        x='experience_years',
        y=st.session_state.salCol,
        markers=True,
        title='Relationship Between Years of Experience and Average Salary',
        labels={'experience_years': 'Years of Experience', st.session_state.salCol: 'Average Salary (USD)'}
    )
    figExp.update_traces(
        line=dict(color='green', width=3),
        marker=dict(size=10, color='darkgreen'),
        hovertemplate='Experience: %{x} years<br>Avg Salary: $%{y:,.0f}<extra></extra>'
    )
    figExp.update_layout(
        xaxis_title='Years of Experience Required',
        yaxis_title='Average Salary (USD)',
        hovermode='x'
    )
    st.plotly_chart(figExp, use_container_width=True)

    min_exp = expSalary['experience_years'].min()
    max_exp = expSalary['experience_years'].max()
    min_sal_exp = expSalary[expSalary['experience_years'] == min_exp][st.session_state.salCol].values[0] if len(expSalary) > 0 else 0
    max_sal_exp = expSalary[expSalary['experience_years'] == max_exp][st.session_state.salCol].values[0] if len(expSalary) > 0 else 0

    st.info(f"""
What this chart tells you:
- Salaries increase with experience, but not linearly.
- Professionals with {max_exp}+ years of experience earn approximately \${max_sal_exp:,.0f}, compared to \${min_sal_exp:,.0f} for entry-level roles.
- The biggest salary jumps tend to occur after the 5-year mark.
""")

    with st.expander("View experience vs salary data"):
        st.dataframe(expSalary, use_container_width=True)
else:
    st.info("Not enough experience data extracted — skipping this chart.")

# ============================================================
# Chart 4.5: Salary impact of skills (new feature)
# Chart 4.5: 技能对薪资的影响（新增功能）
# Show which skills have the highest salaries
# 展示哪些技能对应的薪资最高
# ============================================================
st.subheader("Salary Impact of Key Skills")

if 'skills_found' in filteredDf.columns and len(filteredDf) > 5:
    skillSalDf = pd.DataFrame()
    for skill in topSkills:
        skill_name = skill[0]
        skillData = filteredDf[filteredDf['skills_found'].apply(lambda x: skill_name in x)]
        if len(skillData) >= 3:
            avg_sal = skillData[st.session_state.salCol].mean()
            median_sal = skillData[st.session_state.salCol].median()
            count = len(skillData)
            # 把 skillSalDf._append({...}) 替换成下面这一行
            skillSalDf = pd.concat([skillSalDf, pd.DataFrame([{
                'Skill': skill_name,
                'Avg Salary': avg_sal,
                'Median Salary': median_sal,
                'Job Count': count
            }])], ignore_index=True)

    if len(skillSalDf) > 0:
        skillSalDf = skillSalDf.sort_values('Avg Salary', ascending=False).head(12)

        figSkillSal = px.bar(
            skillSalDf,
            x='Skill',
            y='Avg Salary',
            title='Average Salary for Jobs Requiring Specific Skills (Top 12)',
            labels={'Skill': 'Skill', 'Avg Salary': 'Average Salary (USD)'},
            color='Avg Salary',
            color_continuous_scale='BuGn',
            text='Avg Salary'
        )
        figSkillSal.update_traces(
            texttemplate='$%{text:,.0f}',
            textposition='outside',
            hovertemplate='Skill: %{x}<br>Avg Salary: $%{y:,.0f}<br>Jobs: %{customdata}<extra></extra>',
            customdata=skillSalDf['Job Count'].values
        )
        figSkillSal.update_layout(
            xaxis_title='Skill',
            yaxis_title='Average Salary (USD)',
            xaxis_tickangle=-30
        )
        st.plotly_chart(figSkillSal, use_container_width=True)

        topSkillSal = skillSalDf.iloc[0]['Skill']
        topSkillSalVal = skillSalDf.iloc[0]['Avg Salary']
        st.info(f"""
What this chart tells you:
- Jobs requiring {topSkillSal} pay the highest average salary at ${topSkillSalVal:,.0f}.
- Skills like cloud platforms (AWS, Azure) and data engineering tools tend to command premium salaries.
- However, job count matters too — some high-paying skills have very few openings.
""")

        with st.expander("View skill salary data"):
            st.dataframe(skillSalDf, use_container_width=True)

# ============================================================
# Chart 5: Education vs salary
# Chart 5: 学历与薪资的关系
# ============================================================
st.subheader("Education vs Salary")

filteredDf['education'] = filteredDf[st.session_state.descCol].apply(getEducation)
eduSalary = filteredDf.groupby('education')[st.session_state.salCol].mean().reset_index()
eduSalary = eduSalary.sort_values(st.session_state.salCol, ascending=False)

figEdu = px.bar(
    eduSalary,
    x='education',
    y=st.session_state.salCol,
    text=st.session_state.salCol,
    title='Average IT Salary by Minimum Education Requirement',
    labels={'education': 'Education Level', st.session_state.salCol: 'Average Salary (USD)'},
    color=st.session_state.salCol,
    color_continuous_scale='Purples'
)
figEdu.update_traces(
    texttemplate='$%{text:,.0f}',
    textposition='outside',
    hovertemplate='Education: %{x}<br>Avg Salary: $%{y:,.0f}<extra></extra>'
)
st.plotly_chart(figEdu, use_container_width=True)

top_edu = eduSalary.iloc[0]['education'] if len(eduSalary) > 0 else "N/A"
top_edu_sal = eduSalary.iloc[0][st.session_state.salCol] if len(eduSalary) > 0 else 0

st.info(f"""
What this chart tells you:
- {top_edu} holders earn the highest average salary at ${top_edu_sal:,.0f}.
- Higher education generally correlates with higher pay, but experience often matters more in IT.
""")

with st.expander("View education vs salary data"):
    st.dataframe(eduSalary, use_container_width=True)

# ============================================================
# ============================================================
# Chart 6: Correlation heatmap
# ============================================================
st.subheader("Correlation Heatmap")

try:
    if 'experience_years' not in filteredDf.columns:
        filteredDf['experience_years'] = filteredDf[st.session_state.descCol].apply(getExperience)
    if 'education' not in filteredDf.columns:
        filteredDf['education'] = filteredDf[st.session_state.descCol].apply(getEducation)

    corrData = filteredDf[[st.session_state.salCol, 'experience_years']].copy()
    eduMapping = {'PhD': 5, 'Master': 4, 'Bachelor': 3, 'Associate': 2, 'Not Specified': 1}
    corrData['education_level'] = filteredDf['education'].map(eduMapping)
    corrData = corrData.dropna()
    
    if len(corrData) > 3:
        corrMatrix = corrData.corr()
        figCorr = px.imshow(
            corrMatrix,
            text_auto=True,
            aspect="auto",
            title="Correlation Heatmap (values closer to 1 or -1 indicate stronger relationships)",
            color_continuous_scale='RdBu_r',
            zmin=-1,
            zmax=1
        )
        figCorr.update_layout(height=500)
        st.plotly_chart(figCorr, use_container_width=True)
    else:
        st.info("Not enough data to generate the correlation heatmap. Try uploading more data.")
except:
    st.info("Could not generate correlation heatmap. Not enough valid data available.")

# ============================================================
# Chart 7: Highest paying skills
# Chart 7: 薪资最高的技能
# ============================================================
st.subheader("Highest Paying Skills")

# Use unified getSkills function, removed duplicate getSkillsForSal
# 使用统一的 getSkills 函数，删除重复的 getSkillsForSal
if 'skills_found' not in filteredDf.columns:
    filteredDf['skills_found'] = filteredDf.apply(getSkills, axis=1)

salCol = st.session_state.salCol
skillSalData = {}
for idx, row in filteredDf.iterrows():
    for skill in row['skills_found']:
        if skill not in skillSalData:
            skillSalData[skill] = []
        skillSalData[skill].append(row[salCol])

skillAvgSal = {}
for skill, salaries in skillSalData.items():
    if len(salaries) >= 5:
        skillAvgSal[skill] = sum(salaries) / len(salaries)

highPaySkills = pd.DataFrame(
    list(skillAvgSal.items()),
    columns=['Skill', 'Avg_Salary']
).sort_values('Avg_Salary', ascending=False).head(15)

figHighPay = px.bar(
    highPaySkills.sort_values('Avg_Salary', ascending=True),
    x='Avg_Salary',
    y='Skill',
    orientation='h',
    title='Top 15 IT Skills with the Highest Average Salary',
    labels={'Avg_Salary': 'Average Salary (USD)', 'Skill': ''},
    text='Avg_Salary',
    color='Avg_Salary',
    color_continuous_scale='Reds'
)
figHighPay.update_traces(
    texttemplate='$%{text:,.0f}',
    textposition='outside',
    hovertemplate='Skill: %{y}<br>Avg Salary: $%{x:,.0f}<extra></extra>'
)
figHighPay.update_layout(height=500)
st.plotly_chart(figHighPay, use_container_width=True)

top_highpay = highPaySkills.iloc[0]['Skill'] if len(highPaySkills) > 0 else "N/A"
top_highpay_sal = highPaySkills.iloc[0]['Avg_Salary'] if len(highPaySkills) > 0 else 0

st.info(f"""
What this chart tells you:
- {top_highpay} is the highest-paying skill, with an average salary of ${top_highpay_sal:,.0f}.
- Specializing in these skills can significantly boost your earning potential.
""")

with st.expander("View highest paying skills data"):
    st.dataframe(highPaySkills, use_container_width=True)

# ============================================================
# Core insights summary
# ============================================================
st.divider()
st.subheader("Core Insights")

totalJobs = len(filteredDf)
avgSal = filteredDf[st.session_state.salCol].mean()
maxSalKpi = filteredDf[st.session_state.salCol].max()
minSalKpi = filteredDf[st.session_state.salCol].min()

aiPct = 0
if 'skills_found' in filteredDf.columns:
    aiCount = sum(1 for skills in filteredDf['skills_found'] if 'AI' in skills)
    aiPct = (aiCount / totalJobs) * 100 if totalJobs > 0 else 0

topState = "N/A"
topStateSal = 0
if 'state' in filteredDf.columns and len(filteredDf) > 0:
    stateStats = filteredDf.groupby('state')[st.session_state.salCol].mean()
    if len(stateStats) > 0:
        topState = stateStats.idxmax()
        topStateSal = stateStats.max()

colA, colB = st.columns(2)
with colA:
    st.markdown(f"""
    Key Findings
    - Total Jobs: {totalJobs}
    - Average Salary: \${avgSal:,.0f}
    - Salary Range: \${minSalKpi:,.0f} - \${maxSalKpi:,.0f}
    """)
with colB:
    st.markdown(f"""
    Insights
    - AI Skill Demand: {aiPct:.1f}% of jobs mention AI
    - Top Paying State: {topState} (${topStateSal:,.0f})
    - Recommendation: Prioritise learning AI, cloud security, and other in-demand skills.
    """)

# ============================================================
# AI Salary Predictor (Simple Linear Regression)
# AI 薪资预测器（简单线性回归）
# ============================================================
st.divider()
st.subheader(" Interactive Salary Predictor (Experience & Skill Count)")

try:
    from sklearn.linear_model import LinearRegression
    import numpy as np
    
    # Prepare training data  # 准备训练数据
    pred_df = filteredDf.copy()
    # Count the number of skills per job  # 计算每个岗位的技能数量
    pred_df['skill_count'] = pred_df['skills_found'].apply(len)
    # Extract years of experience  # 提取经验年限
    pred_df['exp_year'] = pred_df[st.session_state.descCol].apply(getExperience)
    
    # Drop rows with missing values  # 丢弃缺失值
    train_data = pred_df[[st.session_state.salCol, 'exp_year', 'skill_count']].dropna()
    
    if len(train_data) > 10:
        X = train_data[['exp_year', 'skill_count']]
        y = train_data[st.session_state.salCol]
        
        model = LinearRegression()
        model.fit(X, y)
        
        col_left, col_right = st.columns([1, 2])
        with col_left:
            # Sliders for user input  # 用户滑动输入
            exp_input = st.slider("Years of Experience", 0, 20, 3)
            skill_input = st.slider("Number of Skills Mastered", 0, 15, 5)
            
            # Make prediction  # 预测
            pred_salary = model.predict([[exp_input, skill_input]])[0]
            st.metric(" Predicted Annual Salary", f"${pred_salary:,.0f}")
        
        with col_right:
            st.caption("💡 Model: Simple Linear Regression trained on current dataset.")
            st.caption(f"Model Formula: Salary = {model.intercept_:.0f} + {model.coef_[0]:.0f}*Experience + {model.coef_[1]:.0f}*Skill_Count")
            st.caption("(For reference only. Real market conditions depend on multiple factors.)")
    else:
        st.info("Not enough valid data to train the prediction model. Make sure your dataset contains job descriptions with years of experience mentioned (e.g. '5 years'). Try uploading a larger dataset.")
except ImportError:
    st.warning("scikit-learn not installed. Please run 'pip install scikit-learn' to enable this feature.")
except Exception as e:
    st.warning(f"Predictor failed to start (other features remain functional): {e}")
# ============================================================
# Footer
# ============================================================
st.divider()
if st.session_state.useUpload:
    st.caption("Data Source: Uploaded file | Tools: Python, Streamlit, Pandas, Plotly")
else:
    st.caption("Data Source: Indeed.com | Tools: Python, Streamlit, Pandas, Plotly")
