from src.query_router import process_query_stream, generate_meta_analysis_response

query = "양적 연구 논문을 찾아줘"
context_str = """Total Matches: 26
Counts by Volume/Issue:
- Vol 12 / Issue 1: 2 articles
- Vol 12 / Issue 2: 2 articles
- Vol 12 / Issue 4: 3 articles
- Vol 13 / Issue 3: 3 articles
- Vol 13 / Issue 4: 4 articles
- Vol 14 / Issue 1: 4 articles
- Vol 14 / Issue 2: 2 articles
- Vol 14 / Issue 3: 3 articles
- Vol 14 / Issue 4: 3 articles

Detailed List:
- Title: Academic Stress of Native American Undergraduates: The Role of Ethnic Identity, Cultural Congruity, and Self-Beliefs | Vol: 12 Issue: 1
- Title: Are Non-Native English Speaking Students Disadvantaged in College Experiences and Cognitive Outcomes? | Vol: 14 Issue: 3
- Title: Are We Ready: Faculty Perceptions of Postsecondary Students With Learning Disabilities at a Historically Black University | Vol: 12 Issue: 4
- Title: Beyond the Numbers: An Examination of Diverse Interactions in Law School | Vol: 12 Issue: 1
- Title: College Undermatching, Bachelor’s Degree Attainment, and Minority Students | Vol: 14 Issue: 2
- Title: Demanding Attention: An Exploration of Institutional Characteristics of Recent Student Demands | Vol: 14 Issue: 1
- Title: Discrimination, Diversity, and Sense of Belonging: Experiences of Students of Color | Vol: 14 Issue: 1
- Title: Diverse Pathways to Graduate Education Attainment | Vol: 13 Issue: 4
- Title: Effect of Accessing Supports on Higher Education Persistence of Students With Disabilities | Vol: 14 Issue: 3
- Title: Examining Construct Validity of the Scale of Native Americans Giving Back | Vol: 14 Issue: 4
- Title: Examining College Students’ Multiple Social Identities of Gender, Race, and Socioeconomic Status: Implications for Intergroup and Social Justice Attitudes | Vol: 12 Issue: 4
- Title: Examining the Factors Associated With College-Related Career Outcome Expectations for Heterosexual and LGBQ Students | Vol: 14 Issue: 1
- Title: Expanding the Reach of Intergroup Dialogue: A Quasi-Experimental Study of Two Teaching Methods for Undergraduate Multicultural Courses | Vol: 13 Issue: 3
- Title: Faculty Attitudes Toward College Students With Criminal Records | Vol: 13 Issue: 4
- Title: Is Campus Diversity Related to Latinx Student Voter Turnout in Presidential Elections? | Vol: 13 Issue: 3
- Title: Just Joking? White College Students’ Responses to Different Types of Racist Comments | Vol: 12 Issue: 4
- Title: Measuring College Students’ Leadership Engagement in Advocacy | Vol: 13 Issue: 3
- Title: Mixed-Reality Simulations to Build Capacity for Advocating for Diversity, Equity, and Inclusion in the Geosciences | Vol: 14 Issue: 4
- Title: Outcomes for Underrepresented and Misrepresented College Students in Service-Learning Classes: Supporting Agents of Change | Vol: 14 Issue: 3
- Title: Predicting the Quality of Black Women Collegians’ Relationships With Faculty at a Public Historically Black University | Vol: 12 Issue: 2
- Title: Student Perceptions of the Climate for Diversity: The Role of Student–Faculty Interactions | Vol: 13 Issue: 4
- Title: Student–Faculty Interactions and Psychosociocultural Influences as Predictors of Engagement Among Black College Students | Vol: 14 Issue: 2
- Title: The Within-Group Differences in LGBQ College Students’ Belongingness, Institutional Commitment, and Outness | Vol: 14 Issue: 1
- Title: Understanding the Role of Collective Racial Esteem and Resilience in the Development of Asian American Leadership Self-Efficacy | Vol: 13 Issue: 4
- Title: Unwelcome on Campus? Predictors of Prejudice Against International 주재국 Students | Vol: 12 Issue: 2
- Title: Weekly Growth of Student Engagement During a Diversity and Social Justice Course: Implications for Course Design and Evaluation | Vol: 14 Issue: 4
"""

print("Testing Gemini generation directly...")
try:
    ans = generate_meta_analysis_response(query, context_str)
    print("SUCCESS!")
    print(ans)
except Exception as e:
    print(f"FAILED: {e}")
