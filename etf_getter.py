import time
import datetime
from datetime import date
import dateutil
from selenium import webdriver
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import natsort
import glob
import matplotlib.pyplot as plt
import os, sys
import shutil
import argparse
import yaml
import requests
#import etfwiz as ew
import ast
import warnings

def scrape_etf(etf, last_update):
    new_update = None
#last_update = None
    current_time = datetime.datetime.now()
    if last_update:
        last_update = datetime.datetime.strptime(last_update, "%m-%d-%Y %H:%M:%S")
    print(etf, '- Scrape, last updated at', last_update)
    browser = Firefox(options=options)
    browser.get(etf_config[etf]['url'])
    if 'steps' in etf_config[etf]:
        for step in etf_config[etf]['steps']:
            try:
                wait = WebDriverWait(browser, 10)
                wait.until(EC.element_to_be_clickable((etf_config[etf]['steps'][step]['by'], etf_config[etf]['steps'][step]['locator'])))
                button = browser.find_element(etf_config[etf]['steps'][step]['by'], etf_config[etf]['steps'][step]['locator'])
                button.send_keys(Keys.RETURN)
                time.sleep(2)
            except TimeoutException:
                print("\tERROR: Selenium timeout for element", etf_config[etf]['steps'][step]['locator'])
                browser.close()
                return new_update
            except NoSuchElementException:
                print("\tERROR: Selenium No Such Element", etf_config[etf]['steps'][step]['locator'])
                browser.close()
                return new_update
    try:
        date_field = browser.find_element(By.XPATH, etf_config[etf]['date_field']).text
    except NoSuchElementException:
        print("\tERROR: Selenium No Such Element", etf_config[etf]['date_field'])
        browser.close()
        return new_update

    date_field = date_field[len(etf_config[etf]['date_header']):]
    holdings_date = datetime.datetime.strptime(date_field, etf_config[etf]['date_format']).date()
    print('\tWebsite As Of Date:', holdings_date)
    if last_update is None or last_update.date() < holdings_date:
        write_file = etf+'_'+holdings_date.strftime('%m-%d-%Y')+'.'+etf_config[etf]['type']
        os.chdir('files')
        filenames = natsort.natsorted(glob.glob('*.'+etf_config[etf]['type']))
        os.chdir('..')
        if not write_file in filenames:
            if 'table' in etf_config[etf]:
                tbl = browser.find_element(etf_config[etf]['table_by'], etf_config[etf]['table']).get_attribute('outerHTML')
                df = pd.read_html(tbl)
                loader_columns = loader_map[etf_config[etf]['loader']]
                dfw = df[0][loader_columns].copy()
                dfw.dropna(how='any', inplace=True)
                dfw.columns = ['Ticker', 'Name', 'Shares']
                dfw['Date'] = holdings_date.strftime('%m-%d-%Y')
                dfw['Shares'] = dfw['Shares'].astype(str)
                dfw['Shares'] = dfw['Shares'].apply(lambda x: x.replace(',',''))
                dfw['Shares'] = dfw['Shares'].apply(lambda x: x.split('.')[0])

                dfw.to_csv('files/'+write_file)
                print('\tRetrieved', write_file, 'at', current_time.strftime("%m-%d-%Y %H:%M:%S"))
                new_update = current_time.replace(month=holdings_date.month, day=holdings_date.day, year=holdings_date.year).strftime("%m-%d-%Y %H:%M:%S")
            else:
                print('\t'+current_time.strftime("%m-%d-%Y %H:%M:%S")+' Error no table identified for '+etf_config[etf])
        else:
            print('\tFile skipped. Requested file already exists: '+write_file)
    else:
        print('\t'+etf+' skipped. Already scraped for as of date')

    browser.close()
    return new_update
#End scrape_etf

def click_etf(etf, last_update):
    new_update = None
    current_time = datetime.datetime.now()
    if last_update:
        last_update = datetime.datetime.strptime(last_update, "%m-%d-%Y %H:%M:%S")
    print(etf, '- Click, last updated at', last_update)
    if 'steps' in etf_config[etf]:
        #remove all files from download directory
        os.chdir('downloads')
        filenames = natsort.natsorted(glob.glob('*.'+etf_config[etf]['type']))
        if filenames:
            for file in filenames:
                print('\tDeleting:', file)
                os.remove(file)
        browser = Firefox(options=options)
        browser.get(etf_config[etf]['url'])
        if 'steps' in etf_config[etf]:
            for step in etf_config[etf]['steps']:
                try:
                    wait = WebDriverWait(browser, 10)
                    wait.until(EC.element_to_be_clickable((etf_config[etf]['steps'][step]['by'], etf_config[etf]['steps'][step]['locator'])))
                    button = browser.find_element(etf_config[etf]['steps'][step]['by'], etf_config[etf]['steps'][step]['locator'])
                    button.send_keys(Keys.RETURN)
                    time.sleep(2)
                except TimeoutException:
                    print("\tERROR: Selenium timeout for element", etf_config[etf]['steps'][step]['locator'])
                    browser.close()
                    os.chdir('..')
                    return new_update
                except NoSuchElementException:
                    print("\tERROR: Selenium No Such Element", etf_config[etf]['steps'][step]['locator'])
                    browser.close()
                    os.chdir('..')
                    return new_update
        try:
            date_field = browser.find_element(By.XPATH, etf_config[etf]['date_field']).text
        except NoSuchElementException:
            print("\tERROR: Selenium No Such Element", etf_config[etf]['date_field'])
            browser.close()
            os.chdir('..')
            return new_update

        date_field = date_field[len(etf_config[etf]['date_header']):]
        if etf_config[etf]['loader'] == 'franklin':
            date_field = date_field.split(' ')[0]
        # holdings_date = datetime.datetime.strptime(date_field, etf_config[etf]['date_format']).date()
        holdings_date = dateutil.parser.parse(date_field).date()
        print('\tWebsite As Of Date:', holdings_date)
        if last_update is None or last_update.date() < holdings_date:
            write_file = etf+'_'+holdings_date.strftime('%m-%d-%Y')+'.'+etf_config[etf]['type']
            filenames = natsort.natsorted(glob.glob('*.'+etf_config[etf]['type']))
#            loader_columns = loader_map[etf_config[etf]['loader']]
            if filenames and len(filenames) == 1:
                if etf_config[etf]['loader'] == 'ark':
                    df = pd.read_csv(filenames[-1], skipfooter=1, converters={'ticker':str}, engine='python')
                    df.dropna(how='any', inplace=True)
                    df['shares'] = df['shares'].astype(str)
                    df['shares'] = df['shares'].apply(lambda x: x.replace(',',''))
                elif etf_config[etf]['loader'] == 'franklin':
                    df = pd.read_excel(filenames[-1], skiprows=6)
                    df.dropna(how='any', inplace=True)
                    df['Quantity'] = df['Quantity'].astype(str)
                    df['Quantity'] = df['Quantity'].apply(lambda x: x.replace(',',''))
                    df['Quantity'] = df['Quantity'].apply(lambda x: x.split('.')[0])
                elif etf_config[etf]['loader'] == 'goldman':
                    with warnings.catch_warnings(record=True):
                        warnings.simplefilter("always")
                        df = pd.read_excel(filenames[-1], skiprows=2, engine="openpyxl")
                        df.dropna(how='any', inplace=True)
                        df['Number of Shares'] = df['Number of Shares'].astype(str)
                        df['Number of Shares'] = df['Number of Shares'].apply(lambda x: x.replace(',',''))
                        df['Number of Shares'] = df['Number of Shares'].apply(lambda x: x.split('.')[0])
                elif etf_config[etf]['loader'] == 'etfmg':
                    col_names = ['Ticker', 'CUSIP', 'Name', 'Shares', 'Market Value', 'Weight']
                    df = pd.read_csv(filenames[-1], skiprows=4, skipfooter=2, names=col_names, header=None, converters={'Shares':str}, engine='python')
#                    df.dropna(how='any', inplace=True)
                    df['Shares'] = df['Shares'].astype(str)
                    df['Shares'] = df['Shares'].apply(lambda x: x.split('.')[0])
                else:
                    print('\tFor '+etf+' no loader specified. ')
                    return new_update

                loader_columns = loader_map[etf_config[etf]['loader']]
                dfw = df[loader_columns].copy()
                dfw.columns = ['Ticker', 'Name', 'Shares']
                dfw['Date'] = holdings_date.strftime('%m-%d-%Y')
                if etf_config[etf]['type'] != 'csv':
                    write_file = write_file.replace(etf_config[etf]['type'], 'csv')
                dfw.to_csv('../files/'+write_file)
                current_time = datetime.datetime.now()
                print('\tRetrieved', write_file, 'at', current_time.strftime("%m-%d-%Y %H:%M:%S"))
                new_update = current_time.replace(month=holdings_date.month, day=holdings_date.day, year=holdings_date.year).strftime("%m-%d-%Y %H:%M:%S")
            else:
                print('\tDownload file not found '+etf)
        else:
            print('\t'+etf+' skipped. Already clicked for as of date')

        browser.close()
        os.chdir('..')
    else:
        print('\tNo steps for '+etf)
    return new_update
#End click_etf

def request_etf(etf, last_update):
    new_update = None
    current_time = datetime.datetime.now()
#    last_update = None
    if last_update:
        last_update = datetime.datetime.strptime(last_update, "%m-%d-%Y %H:%M:%S")
    print(etf, '- Request, last updated at', last_update)
    current_time = datetime.datetime.now()
    holdings_date = None
    if 'steps' in etf_config[etf]:
        #remove all files from download directory
        browser = Firefox(options=options)
        browser.get(etf_config[etf]['date_url'])
        if 'steps' in etf_config[etf]:
            for step in etf_config[etf]['steps']:
                try:
                    wait = WebDriverWait(browser, 10)
                    wait.until(EC.element_to_be_clickable((etf_config[etf]['steps'][step]['by'], etf_config[etf]['steps'][step]['locator'])))
                    button = browser.find_element(etf_config[etf]['steps'][step]['by'], etf_config[etf]['steps'][step]['locator'])
                    button.send_keys(Keys.RETURN)
                    time.sleep(2)
                except TimeoutException:
                    print("\tERROR: Selenium timeout for element", etf_config[etf]['steps'][step]['locator'])
                    browser.close()
                    return new_update
                except NoSuchElementException:
                    print("\tERROR: Selenium No Such Element", etf_config[etf]['steps'][step]['locator'])
                    browser.close()
                    return new_update
        try:
            date_field = browser.find_element(By.XPATH, etf_config[etf]['date_field']).text
        except NoSuchElementException:
            print("\tERROR: Selenium No Such Element", etf_config[etf]['date_field'])
            browser.close()
            return new_update

        date_field = date_field[len(etf_config[etf]['date_header']):]
        holdings_date = datetime.datetime.strptime(date_field, etf_config[etf]['date_format']).date()
        print('\tWebsite As Of Date:', holdings_date)
        browser.close()
    else:
        holdings_date = datetime.datetime.now().date()
    if last_update is None or holdings_date is None or last_update.date() < holdings_date:
        etf_response = requests.get(etf_config[etf]['url'])
        write_file = etf+'_'+holdings_date.strftime('%m-%d-%Y')+'.'+etf_config[etf]['type']
        if etf_response.ok:
            etf_data = etf_response.content
            loader = etf_config[etf]['loader']
            with open(args.path+'downloads/'+write_file, 'wb') as file:
                file.write(etf_data)
                file.close()
                if loader == 'direxion':
                    myCols = ['TradeDate', 'AccountTicker', 'StockTicker', 'SecurityDescription', 'Shares', 'Price', 'MarketValue', 'Cusip', 'HoldingsPercent', 'extra']
                    df = pd.read_csv('downloads/'+write_file, skiprows=6, names=myCols, engine='python')
                    df.drop(columns=['extra'], inplace=True)
                    df.dropna(how='any', inplace=True)
                elif loader == 'statestreet':
                    df = pd.read_excel('downloads/'+write_file, skiprows=4)
                    df.dropna(how='any', inplace=True)
                    df['Shares Held'] = df['Shares Held'].astype(str)
                    df['Shares Held'] = df['Shares Held'].apply(lambda x: x.split('.')[0])
                else:
                    print('\tFor '+etf+' no loader specified. ')
                    return new_update

                loader_columns = loader_map[etf_config[etf]['loader']]
                dfw = df[loader_columns].copy()
                dfw.columns = ['Ticker', 'Name', 'Shares']
                dfw['Date'] = holdings_date.strftime('%m-%d-%Y')
                if etf_config[etf]['type'] != 'csv':
                    write_file = write_file.replace(etf_config[etf]['type'], 'csv')
                dfw.to_csv('files/'+write_file)

                print('\tRetrieved', write_file, 'at', current_time.strftime("%m-%d-%Y %H:%M:%S"))
                new_update = current_time.strftime("%m-%d-%Y %H:%M:%S")
        else:
            print('\tFor '+etf+' Bad response code: '+str(etf_response))
    else:
        print('\t'+etf+' skipped. Already requested for as of date')
    return new_update
#End request_etf

#Begin main
loader_map = {
    'ishares': ['Ticker', 'Name', 'Shares'],
    'proshares': ['Ticker', 'Description', 'Shares/Contracts'],
    'ark': ['ticker', 'company', 'shares'],
    'globalx': ['Ticker', 'Name', 'Shares Held'],
    'sprott': ['Symbol', 'Security', 'Quantity'],
    'ftportfolios': [1, 0, 4],
    'statestreet': ['Ticker', 'Name', 'Shares Held'],
    'direxion': ['StockTicker', 'SecurityDescription', 'Shares'],
    'franklin': ['Ticker', 'Security Name', 'Quantity'],
    'goldman': ['Ticker', 'Description', 'Number of Shares'],
    'etfmg': ['Ticker', 'Name', 'Shares']
}

print('\nStart etfgetter.py:', datetime.datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
parser = argparse.ArgumentParser()
parser.add_argument("--headless", help="selenium will not launch a browser", action="store_true")
parser.add_argument("-p", "--path", help="working path")
parser.add_argument("-l", "--list", help="space delimited list of ETFs to retrieve instead all in etfconfig.yml")
args=parser.parse_args()
if args.path:
    os.chdir(args.path)
else:
    args.path = os.getcwd()+'/'
options = Options()
options.set_preference('browser.download.folderList', 2)
options.set_preference('browser.download.manager.showWhenStarting', False)
options.set_preference('browser.helperApps.neverAsk.saveToDisk', 'application/octet-stream')
options.set_preference('browser.download.dir', args.path+'downloads')
#print(options.__dict__)
if args.headless:
    options.add_argument("-headless")
    
etf_config = yaml.safe_load(open("etfconfig.yml"))
with open('last_updates.txt', 'r') as f:
    last_updates = ast.literal_eval(f.read())

for etf in etf_config:
    if not args.list or etf in args.list:
        if etf_config[etf]['method'] == 'request':
            new_update = request_etf(etf, last_updates[etf])
            if new_update:
                last_updates[etf] = new_update
        elif etf_config[etf]['method'] == 'click':
            new_update = click_etf(etf, last_updates[etf])
            if new_update:
                last_updates[etf] = new_update
        elif etf_config[etf]['method'] == 'scrape':
            new_update = scrape_etf(etf, last_updates[etf])
            if new_update:
                last_updates[etf] = new_update
        else:
            print('This method is not defined:', etf_config[etf]['method'])

f = open('last_updates.txt', 'w')
f.write(str(last_updates))
f.close()
print('\nFinish etfgetter.py:', datetime.datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
