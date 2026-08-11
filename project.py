# ============================================================
# Dashboard with Plotly charts — hover, zoom, filter all work
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np
from collections import Counter

# ============================================================
# Load default data (308 records after cleaning)
# ============================================================
@st.cache_data
def loadDefault():
    # the file is .xls but it's actually CSV, so read_csv works
    df = pd.read_csv('us_software_jobs_500.xls')
    df['salary_avg'] = (df['min_amount'] + df['max_amount']) / 2
    df_clean = df[(df['salary_avg'] >= 30000) & (df['salary_avg'] <= 350000)].copy()
    return df_clean

def getState(location):
    if pd.isna(location):
        return 'Unknown'
    text = str(location).strip()
    if ',' in text:
        parts = text.split(',')
        for part in parts:
            part = part.strip()
            if len(part) == 2 and part.isupper():
                return part
        return parts[-1].strip()
    parts = text.split()
    for part in parts:
        if len(part) == 2 and part.isupper():
            return part
    return parts[-1] if parts else 'Other'

def getEducation(text):
    if pd.isna(text):
        return 'Not Specified'
    text = str(text).lower()
    if 'phd' in text or 'doctorate' in text:
        return 'PhD'
    elif 'master' in text or 'm.s.' in text or 'm.a.' in text:
        return 'Master'
    elif 'bachelor' in text or 'b.s.' in text or 'b.a.' in text or 'bs' in text:
        return 'Bachelor'
    elif 'associate' in text:
        return 'Associate'
    else:
        return 'Not Specified'

skillList = [
    'Python', 'Java', 'JavaScript', 'C++', 'C#', 'Go', 'Ruby', 'Rust',
    'SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis',
    'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins',
    'React', 'Angular', 'Vue', 'Node.js', 'Spring', 'Django', 'Flask',
    'Hadoop', 'Spark', 'Kafka', 'TensorFlow', 'PyTorch',
    'Linux', 'Git', 'DevOps', 'Microservices', 'REST',
    'Machine Learning', 'AI', 'Data Science', 'Cloud', 'Security'
]

def getSkills(row):
    # use skills field if available, otherwise scan description for keywords
    if pd.notna(row.get('skills')) and row['skills'] != 'None' and row['skills'] != '':
        return [s.strip() for s in str(row['skills']).split(',') if s.strip()]
    if pd.isna(row[st.session_state.descCol]):
        return []
    text = str(row[st.session_state.descCol]).lower()
    found = []
    for skill in skillList:
        if skill.lower() in text:
            found.append(skill)
    return found

# ============================================================
# Session state — remembers uploaded data across page reloads
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
# Page setup
# ============================================================
st.set_page_config(page_title="IT Salary Dashboard", layout="wide")
st.title("📊 IT Talent Skill Gap & Salary Visualization")

# ============================================================
# welcome popup — shows once when user first opens the page
# ============================================================
if 'showWelcome' not in st.session_state:
    st.session_state.showWelcome = True

if st.session_state.showWelcome:
    st.divider()
    
    st.markdown("""
    <div style="background-color: #f0f8ff; padding: 30px; border-radius: 12px; border: 2px solid #4CAF50; text-align: center;">
        <h2>👋 Welcome to IT Talent Skill Gap & Salary Dashboard</h2>
        <p style="font-size: 18px; margin-top: 15px;">
            This tool helps you explore IT job market data and identify skill gaps.
        </p>
        <div style="text-align: left; max-width: 600px; margin: 20px auto; font-size: 16px; line-height: 1.8;">
            <b>What you can do here:</b><br>
            📊 View salary distribution and key statistics<br>
            🗺️ Compare salaries across different states<br>
            🔥 Find out which technical skills are most in demand<br>
            🎓 See how education and experience affect salary<br>
            📂 Upload your own CSV or Excel data for analysis<br>
            📥 Download filtered data for further use(coming soon)
        </div>
        <p style="color: #666; font-size: 14px; margin-top: 10px;">
            Data source: Indeed.com | Tools: Python, Streamlit, Plotly, Pandas
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # button to close the popup
    if st.button("🚀 Get Started", key="closeWelcome"):
        st.session_state.showWelcome = False
        st.rerun()
    
    st.stop()

# =====================================================================
# Sidebar: upload data (preview first, apply on button click)
# =====================================================================
st.sidebar.divider()
st.sidebar.subheader("📤 Upload Your Own Data")
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
        
        # try to figure out which columns are what
        salCol = None
        minCol = None
        maxCol = None
        locCol = None
        descCol = None
        
        for col in tempDf.columns:
            col_lower = col.lower()
            if 'min' in col_lower and ('salary' in col_lower or 'amount' in col_lower):
                minCol = col
            elif 'max' in col_lower and ('salary' in col_lower or 'amount' in col_lower):
                maxCol = col
            elif 'salary' in col_lower:
                salCol = col
            elif 'location' in col_lower or 'city' in col_lower or 'state' in col_lower:
                locCol = col
            elif 'description' in col_lower or 'desc' in col_lower:
                descCol = col
        
        # get the salary column
        if salCol is not None:
            tempDf['salary_avg'] = tempDf[salCol]
            colInfo = f"✅ Using column: {salCol} as salary"
            st.session_state.salCol = 'salary_avg'
        elif minCol is not None and maxCol is not None:
            tempDf['salary_avg'] = (tempDf[minCol] + tempDf[maxCol]) / 2
            colInfo = f"✅ Calculated salary from {minCol} and {maxCol}"
            st.session_state.salCol = 'salary_avg'
        else:
            st.sidebar.error("⚠️ Cannot identify salary column.")
            st.stop()
        
        # location column
        if locCol is not None:
            tempDf['location'] = tempDf[locCol]
            locInfo = f"✅ Using column: {locCol} as location"
            st.session_state.locCol = 'location'
        else:
            tempDf['location'] = 'Unknown'
            locInfo = "⚠️ No location column found — using 'Unknown'"
            st.session_state.locCol = 'location'
        
        # description column (skills & experience are extracted from here)
        if descCol is not None:
            tempDf['description'] = tempDf[descCol]
            st.session_state.descCol = 'description'
        else:
            tempDf['description'] = ''
            st.session_state.descCol = 'description'
        
        st.sidebar.info(f"📄 Loaded {len(tempDf)} rows, {len(tempDf.columns)} columns")
        st.sidebar.info(colInfo)
        st.sidebar.info(locInfo)

        st.session_state.tempDf = tempDf.copy()

        if st.sidebar.button("✅ Apply Uploaded Data", type="primary"):
            st.session_state.uploadDf = st.session_state.tempDf.copy()
            st.session_state.useUpload = True
            st.rerun()
            
    except Exception as e:
        st.sidebar.error(f"Failed to read file: {e}")

# ============================================================
# Reset button — go back to default data
# ============================================================
if st.session_state.useUpload:
    if st.sidebar.button("🔄 Reset to Default Data"):
        st.session_state.useUpload = False
        st.session_state.uploadDf = None
        st.session_state.tempDf = None
        st.rerun()

# ============================================================
# Pick which data to use (default or uploaded)
# ============================================================
if st.session_state.useUpload and st.session_state.uploadDf is not None:
    df = st.session_state.uploadDf.copy()
    st.info(f"📊 Using uploaded data: {len(df)} records")
else:
    df = st.session_state.defaultDf.copy()
    st.session_state.useUpload = False
# ============================================================
# dynamic subtitle — changes based on data source
# ============================================================
if st.session_state.useUpload:
    st.markdown("📊 Analysis based on uploaded data")
else:
    st.markdown("📊 Analysis based on 500 software engineer job postings from Indeed.com")
# ============================================================
# Filters: salary range + histogram bins
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

if st.session_state.useUpload:
    st.sidebar.caption("📌 Data source: Uploaded file")
else:
    st.sidebar.caption("📌 Data source: Indeed.com (default)")

# ============================================================
# KPI cards
# ============================================================
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📊 Total Jobs", len(filteredDf))
col2.metric("💰 Average Salary", f"${filteredDf[st.session_state.salCol].mean():,.0f}")
col3.metric("📈 Highest Salary", f"${filteredDf[st.session_state.salCol].max():,.0f}")
col4.metric("📉 Lowest Salary", f"${filteredDf[st.session_state.salCol].min():,.0f}")
col5.metric("📊 Median Salary", f"${filteredDf[st.session_state.salCol].median():,.0f}")
st.divider()

# ============================================================
# Chart 1: Salary distribution
# ============================================================
st.subheader("📈 Salary Distribution")
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


with st.expander("📊 View salary distribution data"):
    st.dataframe(filteredDf[[st.session_state.salCol]].describe(), use_container_width=True)

# ============================================================
# Chart 2: Average salary by state
# ============================================================
st.subheader("🗺️ Average Salary by State")

filteredDf['state'] = filteredDf[st.session_state.locCol].apply(getState)
stateStats = filteredDf.groupby('state').agg(
    avg_salary=(st.session_state.salCol, 'mean'),
    job_count=(st.session_state.salCol, 'count')
).sort_values('avg_salary', ascending=False).reset_index()

topStates = stateStats.head(10)

sortOrder = st.radio("Sort Order", ["Descending (High → Low)", "Ascending (Low → High)"], horizontal=True, index=0)
ascFlag = (sortOrder == "Ascending (Low → High)")
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

with st.expander("📊 View state salary data"):
    st.dataframe(topStates, use_container_width=True)

# ============================================================
# compare stuff — pick two things and see salary diff
# ============================================================
st.subheader("📊 Compare Analysis")

# make sure the columns we need exist before comparing
if 'state' not in filteredDf.columns:
    filteredDf['state'] = filteredDf[st.session_state.locCol].apply(getState)
if 'education' not in filteredDf.columns:
    filteredDf['education'] = filteredDf[st.session_state.descCol].apply(getEducation)
if 'skills_found' not in filteredDf.columns:
    filteredDf['skills_found'] = filteredDf.apply(getSkills, axis=1)

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
            colX.metric(f"📍 {stateA} Jobs", len(dataA))
            colY.metric(f"📍 {stateB} Jobs", len(dataB))
            diffSal = dataA[st.session_state.salCol].mean() - dataB[st.session_state.salCol].mean()
            colZ.metric("💰 Diff", f"${diffSal:,.0f}", delta=f"{'higher' if diffSal > 0 else 'lower'} than {stateB}")
            
            import plotly.graph_objects as go
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
        else:
            st.info("ℹ️ Not enough data for selected states — try others")
    else:
        st.info("ℹ️ Need at least 2 states with data")

elif compType == "Skills":
    allSkills = sorted(set([s for sublist in filteredDf['skills_found'] for s in sublist]))
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
            colX.metric(f"🔧 {skillA} Jobs", len(dataA))
            colY.metric(f"🔧 {skillB} Jobs", len(dataB))
            diffSal = dataA[st.session_state.salCol].mean() - dataB[st.session_state.salCol].mean()
            colZ.metric("💰 Diff", f"${diffSal:,.0f}", delta=f"{'higher' if diffSal > 0 else 'lower'} than {skillB}")
            
            import plotly.graph_objects as go
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
        else:
            st.info("ℹ️ Not enough data for selected skills — try others")
    else:
        st.info("ℹ️ Need at least 2 skills with data")

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
            colX.metric(f"🎓 {eduA} Jobs", len(dataA))
            colY.metric(f"🎓 {eduB} Jobs", len(dataB))
            diffSal = dataA[st.session_state.salCol].mean() - dataB[st.session_state.salCol].mean()
            colZ.metric("💰 Diff", f"${diffSal:,.0f}", delta=f"{'higher' if diffSal > 0 else 'lower'} than {eduB}")
            
            import plotly.graph_objects as go
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
        else:
            st.info("ℹ️ Not enough data for selected education levels")
    else:
        st.info("ℹ️ Need at least 2 education levels with data")

# ============================================================
# Chart 3: Most in-demand skills
# ============================================================

filteredDf['skills_found'] = filteredDf.apply(getSkills, axis=1)

allSkills = []
for skills in filteredDf['skills_found']:
    allSkills.extend(skills)

skillCounter = Counter(allSkills)
topN = st.selectbox("Show Top N Skills", [10, 15, 20], index=1)
st.subheader(f"🔥 Most In-Demand IT Skills (Top {topN})")
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

with st.expander("📊 View skills demand data"):
    st.dataframe(skillsDf, use_container_width=True)

# ============================================================
# Chart 4: Experience vs Salary
# ============================================================
st.subheader("📉 Experience vs Salary")

def getExperience(desc):
    if pd.isna(desc):
        return np.nan
    text = str(desc)
    match = re.search(r'(\d+)\+?\s*year', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return np.nan

filteredDf['experience_years'] = filteredDf[st.session_state.descCol].apply(getExperience)
expData = filteredDf[filteredDf['experience_years'].notna()]
# filter out >30 years because some descriptions have "year 2000" which gets misread as 2000 years
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
    
    with st.expander("📊 View experience vs salary data"):
        st.dataframe(expSalary, use_container_width=True)
else:
    st.info("ℹ️ Not enough experience data extracted — skipping this chart.")

# ============================================================
# Chart 5: Education vs Salary
# ============================================================
st.subheader("🎓 Education vs Salary")

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

with st.expander("📊 View education vs salary data"):
    st.dataframe(eduSalary, use_container_width=True)

# ============================================================
# Correlation Heatmap (experience, education, salary)
# ============================================================
st.subheader("📊 Correlation Heatmap")

if 'experience_years' not in filteredDf.columns:
    filteredDf['experience_years'] = filteredDf[st.session_state.descCol].apply(getExperience)
if 'education' not in filteredDf.columns:
    filteredDf['education'] = filteredDf[st.session_state.descCol].apply(getEducation)

corrData = filteredDf[[st.session_state.salCol, 'experience_years']].copy()
eduMapping = {'PhD': 5, 'Master': 4, 'Bachelor': 3, 'Associate': 2, 'Not Specified': 1}
corrData['education_level'] = filteredDf['education'].map(eduMapping)
corrData = corrData.dropna()
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

# ============================================================
# Chart 6: Highest paying skills
# ============================================================
st.subheader("💰 Highest Paying Skills")

def getSkillsForSal(row):
    if pd.notna(row.get('skills')) and row['skills'] != 'None' and row['skills'] != '':
        return [s.strip() for s in str(row['skills']).split(',') if s.strip()]
    if pd.isna(row[st.session_state.descCol]):
        return []
    text = str(row[st.session_state.descCol]).lower()
    found = []
    skillListLocal = [
        'Python', 'Java', 'JavaScript', 'C++', 'C#', 'Go', 'Ruby', 'Rust',
        'SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis',
        'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins',
        'React', 'Angular', 'Vue', 'Node.js', 'Spring', 'Django', 'Flask',
        'Hadoop', 'Spark', 'Kafka', 'TensorFlow', 'PyTorch',
        'Linux', 'Git', 'DevOps', 'Microservices', 'REST',
        'Machine Learning', 'AI', 'Data Science', 'Cloud', 'Security'
    ]
    for skill in skillListLocal:
        if skill.lower() in text:
            found.append(skill)
    return found

if 'skills_found' not in filteredDf.columns:
    filteredDf['skills_found'] = filteredDf.apply(getSkillsForSal, axis=1)

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

with st.expander("📊 View highest paying skills data"):
    st.dataframe(highPaySkills, use_container_width=True)

# ============================================================
# Core Insights
# ============================================================
st.divider()
st.subheader("💡 Core Insights")

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
    **📌 Key Findings**
    - **Total Jobs**: {totalJobs}
    - **Average Salary**: ${avgSal:,.0f}
    - **Salary Range**: ${minSalKpi:,.0f} - ${maxSalKpi:,.0f}
    """)
with colB:
    st.markdown(f"""
    **🎯 Insights**
    - **AI Skill Demand**: {aiPct:.1f}% of jobs mention AI
    - **Top Paying State**: {topState} (${topStateSal:,.0f})
    - **Recommendation**: Prioritise learning AI, cloud security, and other in-demand skills.
    """)

# ============================================================
# Footer
# ============================================================
st.divider()
st.caption("📌 Data Source: Indeed.com | Tools: Python, Streamlit, Pandas, Plotly")