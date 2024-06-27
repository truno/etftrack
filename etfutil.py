#import sqlite3
import csv
from datetime import datetime, date, timedelta
import natsort
import glob
import os
import shutil
#import pandas as pd
#import numpy as np
import yfinance as yf
import yaml
import pandas_market_calendars as mcal
#import market_dates as md
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
import pickle
from models import db, Fund, Holding, Stock, Price, Snapshot

nyse = mcal.get_calendar('NYSE')
ticker_col = 1
name_col = 2
shares_col = 3
date_col = 4
date_format = '%Y-%m-%d'

def filter_changes(changes, threshold):
    new_changes = []
    for c in changes:
        if abs(c[1]) >= threshold:
            new_changes.append(c)
    return new_changes

def convert_ticker(old, new):
    stocks = db.session.query(Stock).filter(Stock.yahoo_ticker.like('%'+old)).all()
    for s in stocks:
        s.yahoo_ticker = s.yahoo_ticker.split(old)[0]+new
        db.session.commit()
    return len(stocks)

def load_missing_prices():
    stocks = Stock.query.all()
    no_children = [s.yahoo_ticker for s in stocks if not Price.query.filter_by(yahoo_ticker=s.yahoo_ticker).first()]
    update_count = 0
    for c in no_children:
        update_count += update_yf_history(c)
    return update_count

def export_tickers():
    file = open('all_tickers.csv', 'a')
    file.write('fund,fund_ticker,yahoo_ticker,name\n')
    funds = Fund.query.all()
    count = 0
    for f in funds:
#        Create csv file for each fund
        stocks = Stock.query.filter_by(fund_id=f.id).all()
        for s in stocks:
            print(f.ticker+','+s.fund_ticker+','+s.yahoo_ticker+','+s.name)
            file.write(f.ticker+','+s.fund_ticker+','+s.yahoo_ticker+','+s.name+'\n')
            count += 1
#            Write fund.ticker, s.fund_ticker, s.yahoo_ticker, s.name
#        Close file
    file.close()
    return count

def adjacent_market_date(in_date, in_format=date_format, next=True):
#begin last_market_date
    if isinstance(in_date, date):
        valid_date = in_date
    elif isinstance(in_date, str):
        valid_date = datetime.strptime(in_date, in_format).date()
    else:
        raise TypeError('Invalid - only datetime or string objects are allowed')
    if next:
        sdate = valid_date
        edate = valid_date + timedelta(days=7)
        valid_days = nyse.valid_days(start_date=sdate, end_date=edate)
        return valid_days[1].date()
    else:
        sdate = valid_date - timedelta(days=7)
        edate = valid_date - timedelta(days=1)
        valid_days = nyse.valid_days(start_date=sdate, end_date=edate)
        return valid_days[-1].date()
#end last_market_date

def next_market_date(in_date, in_format=date_format):
    return adjacent_market_date(in_date, in_format)

def previous_market_date(in_date, in_format=date_format, next=False):
    return adjacent_market_date(in_date, in_format, next)

def pct_change(a, b):
    return ((a - b) / b) * 100

def reset_all_prices():
    print(datetime.now(), '- Starting stock price update')
    print('Deleting all prices:', db.session.query(Price).delete(), 'rows deleted')
    db.session.commit()
    print(len(Price.query.all()), 'prices loaded after delete all')
#    db.session.flush()
    stocks= Stock.query.all()
    update_count = 0
    for s in stocks:
        update_count += update_yf_history(s.yahoo_ticker)
    print('Post Load Count:', update_count)
    print(datetime.now(), '- Finished stock price update')

def load_current_holdings(path=None, update_prices=False, compress_files=False):
    print('\nStart load_current_holdings -', datetime.now())
    if path:
        os.chdir(path)
    etf_config = yaml.safe_load(open("etfconfig.yml"))
    filenames = natsort.natsorted(glob.glob('files/*.csv'))
    for filename in filenames:
        etf = filename.split('_', 1)[0][6:]
        if etf in etf_config:
            if etf_config[etf]['loader']:
                print()
                print(etf+': '+etf_config[etf]['name'])
                print('\t'+etf_config[etf]['loader']+' loader')
#            ticker_count = load_tickers(fund)
#            print('\tTickers loaded:', ticker_count)
                count = load_holdings(etf, etf_config[etf]['skips'], auto_add=True, move=True)
                print('\t'+str(count)+' holdings loaded')
            else:
                print('ERROR: Loader not defined for', etf)
        else:
            print('ERROR:', etf, 'not found in etfconfig.yml')

    if compress_files:
        print('\nMoving files to Documents')
        etf_zip = 'etftrack_'+date.today().strftime(date_format)
        try:
            shutil.make_archive('../'+etf_zip, 'zip', '../etftrack')
            shutil.move('../'+etf_zip+'.zip', '/Users/georgelucas/Documents/etftrack_backups')
        except shutil.Error as err:
            print('\tFile move error:', err)

    if update_prices:
        print(datetime.now(), '- Starting stock price update')
        update_count = 0
        tickers = db.session.query(Stock.yahoo_ticker).distinct().all()
        for t in tickers:
            update_count += update_yf_history(t[0])
            print(t, update_count)
        print(datetime.now(), '- Finished stock price update')
        print('\tUpdated Rows:', update_count)

    print('\nFinish load_current_holdings -', datetime.now())

def load_holdings(etf, skips=[], last=False, move=False, auto_add=False):
    count = 0
    filenames = natsort.natsorted(glob.glob('files/'+etf+'*.csv'))
#    print(filenames)
    if last:
        filenames = [filenames[-1]]
    fund = Fund.query.filter_by(ticker=etf).first()
    if filenames:
        print('\tLoading Holding Files:')
    else:
        print('\tNo files found')
    for filename in filenames:
        tl = len(etf)
#        observe_date = datetime.strptime(filename[7+tl:17+tl], '%m-%d-%Y')
        observe_date = datetime.strptime(filename[7+tl:17+tl], '%m-%d-%Y').date()
        print('\t\t'+observe_date.strftime('%m-%d-%y'), end='')
#        if len(Snapshot.query.filter_by(fund_id=fund.id).all() == 0):
#            first_load = True
        if len(Holding.query.filter_by(fund=fund.ticker, add_date=observe_date).all()):
            print('\tWarning: Holdings are already loaded for', etf, 'on', observe_date.strftime('%m-%d-%y'))
        else:
            last_date = None
#            print('Has Holdings:', fund.has_holdings, 'First Load:', first_load)
            if fund.has_holdings:
                last_date = db.session.query(Holding).filter(Holding.fund==fund.ticker).order_by(Holding.add_date.desc()).first().add_date
            with open(filename, 'r') as file:
                skipped, adds, drops, changes = [], [], [], []
                reader = csv.reader(file)
                header = []
                header = next(reader)
                for row in reader:
                    if observe_date.strftime('%m-%d-%Y') != row[date_col]:
                        print(row)
                        print('\tWarning: Date mismatch for', row[ticker_col], row[date_col], observe_date)
                    if row[ticker_col] not in skips:
#                        stock = Stock.query.filter_by(fund_ticker=str(row[ticker_col])).first()
                        stock = Stock.query.filter_by(fund=fund.ticker, ticker=str(row[ticker_col])).first()
#                        print('Stock found:', stock)
                        if not stock and auto_add:
                            s = Stock(fund=fund.ticker,
                                      ticker=row[ticker_col],
                                      yahoo_ticker=row[ticker_col],
                                      name = row[name_col])
                            try:
                                db.session.add(s)
                                db.session.commit()
#                                stock = Stock.query.filter_by(fund_ticker=str(row[ticker_col])).first()
                                stock = Stock.query.filter_by(fund=fund.ticker, ticker=str(row[ticker_col])).first()
                                update_yf_history(stock.yahoo_ticker)
                            except Exception as e:
                                print("\tStock add failed for:", s)
                                print(row)
                                db.session.flush()
                                db.session.rollback()
                                raise(e)
                        if stock:
                            # Get last holding
#                            last = db.session.query(Holding).filter(Holding.fund_ticker==stock.fund_ticker).order_by(Holding.add_date.desc()).first()
                            last = db.session.query(Holding).filter(Holding.fund==fund.ticker, Holding.stock==stock.ticker).order_by(Holding.add_date.desc()).first()
                            shares = int(row[shares_col] if row[shares_col].isnumeric() else 0)
                            h = Holding(add_date=observe_date,
                                        created=datetime.now(),
                                        fund=fund.ticker,
                                        stock=stock.ticker,
                                        name=row[name_col],
                                        shares=shares)
                            if last:
                                try:
                                    if last.shares == 0:
                                        h.change_pct = 0
                                    else:
#                                        h.change_pct = ((h.shares - last.shares) / last.shares)*100
                                        h.change_pct = pct_change(h.shares, last.shares)
                                except Exception as e:
                                    print(filename, row, last.shares, h.shares)
                                    print(e)
                                    raise e
                            else:
#                                print(row[ticker_col], end = ',')
#                                h.status = 'Add'
                                adds.append(row[ticker_col])
                            try:
                                db.session.add(h)
                                fund.has_holdings = True
                                db.session.commit()
                                count += 1
                            except Exception as e:
                                print("\tHolding add failed for:", h.__dict__)
                                print(e)
                                db.session.flush()
                                db.session.rollback()
                                raise e
                        else:
                            print('\tWarning: No code identifier for', row[ticker_col])
                    else:
                        skipped.append(row[ticker_col])
#        current_holdings = [h.yahoo_ticker for h in Holding.query.filter_by(add_date=observe_date).all()]
            current_holdings = [h.stock for h in Holding.query.filter_by(fund=fund.ticker, add_date=observe_date).all()]
            if last_date:
#            last_holdings = set([h.yahoo_ticker for h in Holding.query.filter_by(add_date=last_date).all()])
                last_holdings = set([h.stock for h in Holding.query.filter_by(fund=fund.ticker, add_date=last_date).all()])
                drops = list(last_holdings - set(current_holdings))
#            holding_changes = db.session.query(Holding).filter(Holding.change_pct!=0.0, Holding.add_date==observe_date).all()
                holding_changes = db.session.query(Holding).filter(Holding.fund==fund.ticker, Holding.change_pct!=0.0, Holding.add_date==observe_date).all()
#            changes = [(h.yahoo_ticker, h.change_pct) for h in holding_changes]
                changes = [(h.stock, h.change_pct) for h in holding_changes]
                if drops:
                    for d in drops:
                        try:
#                        holding = Holding.query.filter_by(yahoo_ticker=d, add_date=last_date).first()
                            holding = Holding.query.filter_by(fund=fund.ticker, stock=d, add_date=last_date).first()
#                        holding.status = 'Drop'
                            db.session.commit()
                        except:
                            print("\tDrop status change failed for", d)
                            db.session.flush()
                            db.session.rollback()
                print(' Adds:', adds, 'Drops:', drops, 'Changes count', len(changes))
                s = Snapshot(add_date=observe_date,
                         fund=fund.ticker,
                         holdings=pickle.dumps(current_holdings),
                         adds=pickle.dumps(adds),
                         drops=pickle.dumps(drops),
                         changes=pickle.dumps(changes))
                try:
                    db.session.add(s)
                    db.session.commit()
                except:
                    print("\tSnapshot load failed for", s)
                    db.session.flush()
                    db.session.rollback()
            if move:
                shutil.move(filename, 'loaded_files'+filename[5:])

    return count
#end etf_loader

def update_yf_history(yahoo_ticker):
#    cur = con.cursor()
    add_count = 0
#    prices = Price.query.filter_by(yahoo_ticker=yahoo_ticker).all()
    if not len(Price.query.filter_by(yahoo_ticker=yahoo_ticker).all()):
        yft = yf.Ticker(yahoo_ticker)
        yfh = yft.history(start='2022-04-25', timeout=15)
        if len(yfh):
            yfh['market_date'] = yfh.index.strftime(date_format)
            yfh['yahoo_ticker'] = yahoo_ticker
            yfh = yfh.drop(columns=['Dividends', 'Stock Splits'])
            add_count = yfh.to_sql(name='prices', con=db.engine, index=False, if_exists='append')
            if add_count:
                print(' - '+str(add_count)+' prices added for '+yahoo_ticker)
                db.session.commit()
            else:
                print(' - UPDATE FAILED:', yahoo_ticker)
                db.session.flush()
                db.session.rollback()
        else:
            print('\t\tNO YAHOO HISTORY:', yahoo_ticker)
    else:
        print('\t\tPrices already exist, skipping:', yahoo_ticker)

    return add_count
#End update_yf_history

def load_tickers(fund, load_prices=False):
#Start load_tickers
    print('\tLoading stocks for', fund.ticker)
    count = 0

#    file = open('tickers/'+fund.ticker+'_tickers.csv')
    file = open('all_tickers.csv')
    csvreader = csv.reader(file)
    header = next(csvreader)
    rows = []
    for row in csvreader:
#        print(row)
        if row[0] == fund.ticker:
            s = Stock.query.filter_by(fund=fund.ticker, ticker=row[1]).first()
            if not s:
                s = Stock(fund=fund.ticker, ticker=row[1], yahoo_ticker=row[2], name=row[3])
                try:
                    db.session.add(s)
                    db.session.commit()
                    print("\t\tStock added:", s.ticker, s.yahoo_ticker, end="")
                    count += 1
                except Exception as e:
                    print("\t\tError: Stock add failed for ", s)
                    db.session.flush()
                    db.session.rollback()
                    raise e
                if load_prices:
                    update_yf_history(s.yahoo_ticker)
            else:
                print("\t\tStock already loaded:", row)

    return count
#End load_tickers

def load_database(config_file):
#begin load_funds
    filenames = os.listdir('loaded_files')
    print('Moving files')
    filenames = natsort.natsorted(glob.glob('loaded_files/*.csv'))
    for filename in filenames:
        shutil.move(filename, 'files')

    etf_config = yaml.safe_load(open(config_file))
    for etf in etf_config:
        print('\nInserting', etf)
        fund = Fund(ticker=etf, name=etf_config[etf]['name'])
        try:
            db.session.add(fund)
            db.session.commit()
        except Exception as e:
            print("\tError: Fund add failed for ", etf)
            db.session.flush()
            db.session.rollback()
            raise e
#            pass
        if etf_config[etf]['loader']:
            print(etf+': '+etf_config[etf]['name'])
            print('\t'+etf_config[etf]['loader']+' loader')
    #        rip_tickers(cur, etf_config[etf]['ticker'], etf_config[etf]['loader'])
            ticker_count = load_tickers(fund, load_prices=True)
            print('\t'+etf, 'tickers loaded:', ticker_count)
            count = load_holdings(fund.ticker, etf_config[etf]['skips'],
                                   move=True, auto_add=True)
            if count:
                print('\t'+etf, 'Holdings loaded: ', count)
            else:
                print('\tNo holdings loaded for', etf)
        else:
            print()
            print('No Loader for '+etf+': '+etf_config[etf]['name'])

#        if update_prices:
#            print(datetime.now(), '- Starting stock price update')
#            update_count = 0
#            tickers = db.session.query(Stock.yahoo_ticker).distinct().all()
#            for t in tickers:
#                update_count += update_yf_history(t[0])
#                print(t, update_count)
#            print(datetime.now(), '- Finished stock price update')
#            print('\tUpdated Rows:', update_count)
#end load_funds
