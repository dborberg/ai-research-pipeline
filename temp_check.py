import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('sqlite:///data/articles.db')
df = pd.read_sql_query('SELECT * FROM articles', engine)
df['ai_score'] = pd.to_numeric(df['ai_score'], errors='coerce')
count_all = len(df)
count_high = int((df['ai_score'] >= 7).sum())
with open('data/check_counts.txt', 'w') as f:
    f.write(f'total={count_all}\nhigh_score={count_high}\n')
print('done')
