import streamlit as st
import pandas as pd
import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- Helper Functions ---

def scrape_linkedin_jobs(query, location):
    """Scrapes an extended list of public LinkedIn jobs by deep scrolling and clicking load buttons."""
    jobs = []
    url = f"https://www.linkedin.com/jobs/search?keywords={query.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=45000)
            
            # --- EXTENDED SCROLLING LOGIC ---
            # Loops 6 times, scrolling to trigger infinite data loading layers
            for i in range(6): 
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2) 
                
                # Clicks the public "See more jobs" button if it appears
                try:
                    see_more_button = page.locator("button.infinite-scroller__button")
                    if see_more_button.is_visible():
                        see_more_button.click()
                        time.sleep(2)
                except:
                    pass 
                    
            html = page.content()
        except Exception as e:
            html = ""
        finally:
            browser.close()
        
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    job_cards = soup.find_all('div', class_='base-card')
    
    for card in job_cards:
        try:
            title_el = card.find('h3', class_='base-search-card__title')
            company_el = card.find('h4', class_='base-search-card__subtitle')
            link_el = card.find('a', class_='base-card__full-link')
            
            if title_el and company_el and link_el:
                title = title_el.text.strip()
                company = company_el.text.strip()
                link = link_el['href']
                
                metadata = card.find('span', class_='job-search-card__salary-info')
                salary_text = metadata.text.strip() if metadata else "Not Listed"
                
                jobs.append({
                    "Title": title,
                    "Company": company,
                    "Link": link,
                    "Raw_Salary": salary_text,
                    "Description": ""
                })
        except Exception:
            continue
            
    return jobs

def scrape_job_description(job_url):
    """Navigates to an individual job link to pull the full description."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = context.new_page()
            page.goto(job_url, timeout=20000)
            
            try:
                page.click('button.show-more-less-html__button', timeout=2000)
            except:
                pass
                
            html = page.content()
            browser.close()
        
        soup = BeautifulSoup(html, 'html.parser')
        desc_div = soup.find('div', class_='show-more-less-html__markup')
        return desc_div.text.strip() if desc_div else ""
    except:
        return ""

def extract_min_salary(salary_str):
    """Attempts to pull a numeric baseline from string formats like '$120,000'"""
    numbers = re.findall(r'\b\d{1,3}(?:,\d{3})*\b', salary_str)
    if numbers:
        return int(numbers[0].replace(',', ''))
    return 0

# --- UI Layout & Custom Styling ---

st.set_page_config(page_title="LinkedIn Premium Job Hunter", layout="wide", initial_sidebar_state="expanded")

# Custom UI Dark Theme Enhancements
st.markdown("""
    <style>
    .main .block-container {padding-top: 2rem;}
    div.stButton > button:first-child {
        background-color: #0066cc; color: white; border-radius: 8px; width: 100%; font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Premium LinkedIn Job Pipeline")
st.caption("Deep-scans large listings datasets and streams approved items to your screen in real time.")
st.write("---")

# --- Sidebar Inputs ---
st.sidebar.header("📋 Target Parameters")
job_query = st.sidebar.text_input("Job Title / Key Term", "Python Developer")
location = st.sidebar.text_input("Location / Country", "India")

st.sidebar.subheader("🔍 Deep Filtering Rules")

# SALARY CONSTRAINT: Turning this off bypasses mandatory salary filters!
enable_salary = st.sidebar.checkbox("Filter by Minimum Salary", value=False)
if enable_salary:
    min_salary_input = st.sidebar.number_input("Minimum Base Salary ($)", value=80000, step=5000)
else:
    min_salary_input = 0

required_keywords = st.sidebar.text_input("Required Description Keywords (comma separated)", "Bank")

# --- Processing Execution Pipeline ---
if st.sidebar.button("Launch Pipeline Search"):
    
    # Clean Dashboard Metric Displays
    col1, col2, col3 = st.columns(3)
    with col1:
        stat_discovered = st.empty()
        stat_discovered.metric("Discovered Raw Postings", "0")
    with col2:
        stat_scanned = st.empty()
        stat_scanned.metric("Current Progress", "0 / 0")
    with col3:
        stat_matched = st.empty()
        stat_matched.metric("Matched Criteria", "0", delta="0 updates")

    status_message = st.empty()
    progress_bar = st.progress(0)
    
    status_message.info("🌐 Fetching deep job board index from LinkedIn public endpoints...")
    raw_jobs = scrape_linkedin_jobs(job_query, location)
    total_raw = len(raw_jobs)
    
    if total_raw == 0:
        status_message.error("🚨 Zero jobs found or LinkedIn blocked the request packet. Try adjusting your search keywords.")
    else:
        stat_discovered.metric("Discovered Raw Postings", f"{total_raw}")
        status_message.success(f"Successfully cached {total_raw} jobs! Launching deep analysis framework...")
        
        # Stream window layout container
        st.subheader("🚀 Live Streaming Matches")
        table_placeholder = st.empty()
        
        filtered_jobs = []
        
        # Main processing streaming engine loop
        for idx, job in enumerate(raw_jobs):
            current_num = idx + 1
            
            # Clean real-time tracking line
            status_message.text(f"⏳ Currently Analyzing ({current_num}/{total_raw}): {job['Title']} at {job['Company']}")
            stat_scanned.metric("Current Progress", f"{current_num} / {total_raw}")
            progress_bar.progress(current_num / total_raw)
            
            # Rule Evaluation A: Salary Constraint Check
            salary_passes = True
            estimated_salary = extract_min_salary(job['Raw_Salary'])
            if enable_salary:
                if estimated_salary > 0 and estimated_salary < min_salary_input:
                    salary_passes = False
                elif estimated_salary == 0:
                    salary_passes = False

            # Rule Evaluation B: Deep Text Parsing
            keywords_matched = True
            if salary_passes:  
                description = scrape_job_description(job['Link'])
                if required_keywords:
                    kw_list = [k.strip().lower() for k in required_keywords.split(",")]
                    for kw in kw_list:
                        if kw not in description.lower() and kw not in job['Title'].lower():
                            keywords_matched = False
                            break
            else:
                keywords_matched = False

            # Live render matching items immediately 
            if salary_passes and keywords_matched:
                filtered_jobs.append({
                    "Job Title": job['Title'],
                    "Company / Enterprise": job['Company'],
                    "Salary Listed": job['Raw_Salary'],
                    "Application Link": job['Link']
                })
                
                # Update visual spreadsheet component instantly
                df_display = pd.DataFrame(filtered_jobs)
                table_placeholder.dataframe(df_display, use_container_width=True)
                stat_matched.metric("Matched Criteria", f"{len(filtered_jobs)}", delta=f"+{len(filtered_jobs)} Approved")

            # Politeness buffer pause
            time.sleep(1.2)
            
        status_message.success(f"📊 Extraction Complete! Processed {total_raw} targets. Found {len(filtered_jobs)} perfect matches.")
        st.balloons()
