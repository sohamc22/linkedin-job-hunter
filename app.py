import os
import subprocess
import streamlit as st

# --- CLOUD INITIALIZATION ---
@st.cache_resource
def initialize_cloud_browsers():
    try:
        if os.environ.get("STREAMLIT_SERVER_PORT") or os.path.exists("/home/adminuser"):
            subprocess.run(["playwright", "install", "chromium"], check=True)
            subprocess.run(["playwright", "install-deps"], check=True)
    except Exception as e:
        pass

initialize_cloud_browsers()

# --- Core Dependencies ---
import pandas as pd
import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- Helper Functions ---

def scrape_linkedin_jobs(query, location, force_remote=False):
    jobs = []
    
    # If the user checked "Remote", we append it straight to the main search string to help LinkedIn filter early
    final_query = query
    if force_remote and "remote" not in query.lower():
        final_query += " remote"
        
    url = f"https://www.linkedin.com/jobs/search?keywords={final_query.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=45000)
            for i in range(5): 
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2) 
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
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X)")
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
    numbers = re.findall(r'\b\d{1,3}(?:,\d{3})*\b', salary_str)
    if numbers:
        return int(numbers[0].replace(',', ''))
    return 0

# --- Mobile UI Layout Configuration ---

st.set_page_config(page_title="Job Hunter Mobile", layout="wide", initial_sidebar_state="collapsed")

# Inject Custom Mobile Styles WITH COPY/PASTE SUPPORT ENABLED
st.markdown("""
    <style>
    /* CRITICAL: Enforce selectability across the mobile layout */
    * {
        user-select: text !important;
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
    }
    .main .block-container { padding-top: 1rem; padding-left: 0.8rem; padding-right: 0.8rem; }
    div.stButton > button:first-child {
        background-color: #0066cc; color: white; border-radius: 12px; 
        width: 100%; font-size: 18px; padding: 12px; font-weight: bold; height: 50px;
    }
    .mobile-card {
        background-color: #1e222b; border: 1px solid #2d3139; padding: 16px; 
        border-radius: 12px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .mobile-title { color: #ffffff; font-size: 18px; font-weight: bold; margin-bottom: 4px; }
    .mobile-company { color: #a0aec0; font-size: 15px; margin-bottom: 8px; }
    .mobile-salary { display: inline-block; background-color: #2d3748; color: #63b3ed; padding: 4px 8px; border-radius: 6px; font-size: 13px; font-weight: 500; margin-right: 5px; }
    .mobile-badge { display: inline-block; background-color: #2b6cb0; color: #ebf8ff; padding: 4px 8px; border-radius: 6px; font-size: 13px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

st.title("📱 LinkedIn Job Pipeline")
st.caption("Fully adaptive mobile scanner layout with advanced keyword & workplace flexibility logic.")
st.write("---")

# --- Form Fields Placed Directly in Main Page via Expanders ---
with st.expander("⚙️ Adjust Search Parameters & Rules", expanded=True):
    job_query = st.text_input("Job Title / Key Term", "Python Developer")
    location = st.text_input("Location / Country", "India")
    
    st.write("---")
    st.markdown("**🏡 Workplace Settings**")
    filter_remote = st.checkbox("Require Remote Roles", value=False)
    
    st.markdown("**⏰ Job Commitment Type**")
    filter_fulltime = st.checkbox("Require Full-Time roles", value=False)
    filter_parttime = st.checkbox("Require Part-Time roles", value=False)
    
    st.write("---")
    enable_salary = st.checkbox("Filter by Minimum Salary", value=False)
    if enable_salary:
        min_salary_input = st.number_input("Minimum Base Salary ($)", value=80000, step=5000)
    else:
        min_salary_input = 0
        
    required_keywords = st.text_input("Other Required Keywords (comma separated)", "")

st.write("")

# --- Launch Button Execution Framework ---
if st.button("🚀 Launch Pipeline Search"):
    
    col1, col2, col3 = st.columns(3)
    with col1:
        stat_discovered = st.empty()
        stat_discovered.metric("Discovered", "0")
    with col2:
        stat_scanned = st.empty()
        stat_scanned.metric("Scanned", "0")
    with col3:
        stat_matched = st.empty()
        stat_matched.metric("Matched", "0")

    status_message = st.empty()
    progress_bar = st.progress(0)
    
    status_message.info("🌐 Indexing public job layers... This can take 10-15 seconds.")
    raw_jobs = scrape_linkedin_jobs(job_query, location, force_remote=filter_remote)
    total_raw = len(raw_jobs)
    
    if total_raw == 0:
        status_message.error("🚨 Zero jobs matched. Adjust parameters or keywords.")
    else:
        stat_discovered.metric("Discovered", f"{total_raw}")
        status_message.success(f"Processing matches out of {total_raw} items...")
        
        st.subheader("🎯 Matches Found")
        
        table_placeholder = st.empty()
        cards_placeholder = st.container()
        
        filtered_jobs = []
        
        for idx, job in enumerate(raw_jobs):
            current_num = idx + 1
            
            status_message.text(f"⏳ Tracking {current_num}/{total_raw}: {job['Title']}")
            stat_scanned.metric("Scanned", f"{current_num}")
            progress_bar.progress(current_num / total_raw)
            
            # --- FILTER A: SALARY CHECK ---
            salary_passes = True
            estimated_salary = extract_min_salary(job['Raw_Salary'])
            if enable_salary:
                if estimated_salary > 0 and estimated_salary < min_salary_input:
                    salary_passes = False
                elif estimated_salary == 0:
                    salary_passes = False

            # Fetch deep description if Salary check passes
            keywords_matched = True
            if salary_passes:  
                description = scrape_job_description(job['Link'])
                searchable_text = (job['Title'] + " " + description).lower()
                
                # --- FILTER B: WORKPLACE REMOTE CHECK ---
                if filter_remote:
                    # Scans text and listings for common variants of remote work definitions
                    remote_terms = ["remote", "wfh", "work from home", "work-from-home", "telecommute"]
                    if not any(term in searchable_text for term in remote_terms):
                        keywords_matched = False
                
                # --- FILTER C: COMMITMENT TYPE CHECK ---
                if keywords_matched and (filter_fulltime or filter_parttime):
                    type_match = False
                    if filter_fulltime and any(term in searchable_text for term in ["full time", "full-time", "permanent"]):
                        type_match = True
                    if filter_parttime and any(term in searchable_text for term in ["part time", "part-time", "contractor", "internship"]):
                        type_match = True
                    
                    if not type_match:
                        keywords_matched = False
                        
                # --- FILTER D: EXTRA CUSTOM SIDEBAR KEYWORDS ---
                if keywords_matched and required_keywords:
                    kw_list = [k.strip().lower() for k in required_keywords.split(",")]
                    for kw in kw_list:
                        if kw not in searchable_text:
                            keywords_matched = False
                            break
            else:
                keywords_matched = False

            # Render logic upon validation match
            if salary_passes and keywords_matched:
                filtered_jobs.append({
                    "Job Title": job['Title'],
                    "Company": job['Company'],
                    "Salary": job['Raw_Salary'],
                    "Link": job['Link']
                })
                
                df_display = pd.DataFrame(filtered_jobs)
                table_placeholder.dataframe(df_display, use_container_width=True)
                stat_matched.metric("Matched", f"{len(filtered_jobs)}")
                
                # Render clean, selectable HTML mobile UI block card layout on screen
                with cards_placeholder:
                    st.markdown(f"""
                        <div class="mobile-card">
                            <div class="mobile-title">{job['Title']}</div>
                            <div class="mobile-company">🏢 {job['Company']}</div>
                            <div class="mobile-salary">💵 Salary: {job['Raw_Salary']}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    st.link_button("👉 Direct Apply Link", job['Link'], use_container_width=True)
                    st.write("") 

            time.sleep(1.2)
            
        status_message.success(f"📊 Extraction Complete! Found {len(filtered_jobs)} matches.")
        st.balloons()
