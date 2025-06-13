import os
import base64
import requests
from flask import Flask, request, render_template, redirect, flash
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials as GSCreds
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SESSION_SECRET        = os.environ['SESSION_SECRET']
GOOGLE_CREDS_PATH     = os.environ['GOOGLE_CREDS_PATH']
SUMMARY_SHEET_URL     = os.environ['SUMMARY_SHEET_URL']
EBAY_CLIENT_ID        = os.environ['EBAY_CLIENT_ID']
EBAY_CLIENT_SECRET    = os.environ['EBAY_CLIENT_SECRET']

# Fee settings
PLATFORM_FEE_RATE     = 0.12
TRANSACTION_FEE_RATE  = 0.029
TRANSACTION_FEE_FIXED = 0.30

app = Flask(__name__)
app.secret_key = SESSION_SECRET
os.makedirs('tmp', exist_ok=True)

GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def allowed_file(fname):
    return fname.lower().endswith(('xls','xlsx','csv'))

def get_ebay_token():
    auth = base64.b64encode(f'{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}'.encode()).decode()
    resp = requests.post(
        'https://api.ebay.com/identity/v1/oauth2/token',
        headers={
            'Content-Type':'application/x-www-form-urlencoded',
            'Authorization':f'Basic {auth}'
        },
        data={'grant_type':'client_credentials','scope':'https://api.ebay.com/oauth/api_scope'}
    )
    resp.raise_for_status()
    return resp.json()['access_token']

def get_average_price(kw, token):
    resp = requests.get(
        'https://api.ebay.com/buy/browse/v1/item_summary/search',
        headers={'Authorization':f'Bearer {token}'},
        params={'q':kw,'filter':'priceCurrency:USD','limit':'5'}
    )
    if resp.status_code!=200:
        return 0.0
    prices = []
    for itm in resp.json().get('itemSummaries',[]):
        try: prices.append(float(itm['price']['value']))
        except: pass
    return sum(prices)/len(prices) if prices else 0.0

def store_dataframe(df,key):
    path = os.path.join('tmp',f'{key}.pkl')
    df.to_pickle(path)
    return key

def load_dataframe(key):
    return pd.read_pickle(os.path.join('tmp',f'{key}.pkl'))

def update_summary_row(summary_row):
    # convert numpy types to native Python
    clean = []
    for v in summary_row:
        try: clean.append(v.item())
        except: clean.append(v)
    header = [
        'Manifest Name',
        'Total Items',
        'Total Retail Value',
        'Avg. Value/Item',
        'Top Brands',
        'Manifest Cost',
        'Profit Potential',
        'Max Bid Recommendation',
        'Total Revenue',
        'Total Fees',
        'Net Profit',
        'Avg ROI %',
        'Target Margin %'
    ]
    creds  = GSCreds.from_service_account_file(GOOGLE_CREDS_PATH, scopes=GOOGLE_SCOPES)
    client = gspread.authorize(creds)
    sheet  = client.open_by_url(SUMMARY_SHEET_URL)
    try:
        ws = sheet.worksheet('Summary')
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet('Summary',100,20)
    data = ws.get_all_values()
    if not data or data[0]!=header:
        ws.clear()
        ws.append_row(header)
        data = [header]
    kept = [data[0]] + [r for r in data[1:] if r[0]!=clean[0]]
    ws.clear()
    for r in kept: ws.append_row(r)
    ws.append_row(clean)

def get_next_tab_name(sheet,base):
    titles = [w.title for w in sheet.worksheets()]
    if base not in titles: return base
    i=1
    while True:
        name=f"{base} ({i})"
        if name not in titles: return name
        i+=1

@app.route('/',methods=['GET','POST'])
def upload_view():
    if request.method=='POST':
        f=request.files.get('manifest')
        if not f or not allowed_file(f.filename):
            flash('Select a valid Excel/CSV file','danger')
            return redirect(request.url)
        df = pd.read_excel(f) if f.filename.lower().endswith(('xls','xlsx')) else pd.read_csv(f)
        sid=store_dataframe(df,f.filename)
        return render_template('mapping.html',columns=list(df.columns),session_id=sid,filename=f.filename)
    return render_template('upload.html')

@app.route('/process-mapping',methods=['POST'])
def process_mapping():
    sid=request.form['session_id']
    df=load_dataframe(sid)
    df.reset_index(drop=True,inplace=True)
    df=df.loc[:,~df.columns.duplicated()]

    # map columns
    fields=[
        'Listing ID','Listing Title','Category','Product Name','UPC','ASIN',
        'Quantity','Orig. Retail','Cost per Unit','Stock Image','Manifest Name'
    ]
    mapping={f:request.form.get(f) for f in fields if request.form.get(f) in df.columns}
    df.rename(columns={v:k for k,v in mapping.items()},inplace=True)

    # fetch eBay prices
    token=get_ebay_token()
    df['Avg Sold Price']=0.0
    for idx,kw in zip(df.index,df['Product Name']):
        df.at[idx,'Avg Sold Price']=get_average_price(kw,token)

    # base revenue & cost
    df['Total Orig. Retail']=df['Quantity']*df['Orig. Retail']
    tc=request.form.get('total_cost','').strip()
    total_items=df['Quantity'].sum() or 1
    if tc:
        cpu=float(tc)/total_items
        df['Cost per Unit']=cpu
    elif 'Cost per Unit' in df.columns:
        df['Cost per Unit']=pd.to_numeric(df['Cost per Unit'],errors='coerce').fillna(0)
    else:
        df['Cost per Unit']=df['Orig. Retail']

    # shipping & margin
    ship_u=float(request.form.get('shipping_cost','0') or 0)
    targ_m=float(request.form.get('target_margin','20') or 20)/100

    # fees & P&L
    fee_rate=PLATFORM_FEE_RATE+TRANSACTION_FEE_RATE
    df['Fees %']=df['Avg Sold Price']*fee_rate
    df['Fees $']=TRANSACTION_FEE_FIXED
    df['Total Fees/U']=df['Fees %']+df['Fees $']
    df['Net Rev/U']=df['Avg Sold Price']-df['Total Fees/U']-ship_u
    df['Profit/U']=df['Net Rev/U']-df['Cost per Unit']
    df['Profit Potential']=df['Profit/U']*df['Quantity']
    df['ROI %']=df['Profit/U']/df['Cost per Unit'].replace(0,1)*100
    df['Max Bid Recommendation']=df['Net Rev/U']/(1+targ_m)

    # compute summary
    total_retail=df['Total Orig. Retail'].sum()
    avg_value=total_retail/total_items
    manifest_cost=(df['Cost per Unit']*df['Quantity']).sum()
    profit_total=df['Profit Potential'].sum()
    total_revenue=(df['Avg Sold Price']*df['Quantity']).sum()
    total_fees=(df['Total Fees/U']*df['Quantity']).sum()
    avg_roi=df['ROI %'].mean()
    max_bid=df['Max Bid Recommendation'].mean()

    summary=[
        request.form.get('manifest_name','')[:10],    # Manifest Name
        int(total_items),                            # Total Items
        total_retail,                                # Total Retail Value
        avg_value,                                   # Avg. Value/Item
        'TBD',                                       # Top Brands
        manifest_cost,                               # Manifest Cost
        profit_total,                                # Profit Potential
        max_bid,                                     # Max Bid Recommendation
        total_revenue,                               # Total Revenue
        total_fees,                                  # Total Fees
        profit_total,                                # Net Profit
        avg_roi,                                     # Avg ROI %
        targ_m*100                                   # Target Margin %
    ]

    update_summary_row(summary)

    # write detail tab
    creds=GSCreds.from_service_account_file(GOOGLE_CREDS_PATH,scopes=GOOGLE_SCOPES)
    client=gspread.authorize(creds)
    sheet=client.open_by_url(SUMMARY_SHEET_URL)
    tab=get_next_tab_name(sheet,summary[0])
    ws=sheet.add_worksheet(tab,rows=str(len(df)+5),cols="20")
    ws.clear()
    export_cols=[
        'Listing ID','Listing Title','Category','Product Name','UPC','ASIN',
        'Quantity','Orig. Retail','Cost per Unit','Avg Sold Price',
        'Profit Potential','Stock Image'
    ]
    export_cols=[c for c in export_cols if c in df.columns]
    ws.append_row(export_cols)
    ws.append_rows(df[export_cols].fillna('').values.tolist())

    base=SUMMARY_SHEET_URL.split('/edit')[0]
    sheet_url=f"{base}/edit#gid={ws.id}"

    return render_template(
        'result.html',
        summary={  # pass dict keyed by header for template
            header: value for header, value in zip([
                'Manifest Name','Total Items','Total Retail Value','Avg. Value/Item',
                'Top Brands','Manifest Cost','Profit Potential','Max Bid Recommendation',
                'Total Revenue','Total Fees','Net Profit','Avg ROI %','Target Margin %'
            ], summary)
        },
        sheet_url=sheet_url,
        summary_sheet_url=SUMMARY_SHEET_URL,
        data=df.to_dict(orient='records')
    )

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)
