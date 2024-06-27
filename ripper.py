#import sqlite3
import natsort
import glob
import os
import shutil
import csv
import yfinance as yf

def rip_tickers(etf_ticker, skips):
#Start rip_ark_tickers
#    cur = con.cursor()
    print("Loading", etf_ticker)
    filenames = natsort.natsorted(glob.glob('loaded_files/'+etf_ticker+'*.csv'))
#    cur.execute('SELECT id FROM funds WHERE ticker=?', (etf_ticker,))
#    etf_id = cur.fetchone()[0]
    file = filenames[0]
    with open(file, newline='') as f:
        reader = csv.reader(f)
        header = []
        header = next(reader)
        with open('tickers/'+etf_ticker+'_tickers.csv', 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, ['Ticker', 'Yahoo', 'Name'])
            writer.writeheader()
#            print(reader)
            print('Loading tickers: ', end='')
            for row in reader:
                print(row)
                if row[1] not in skips:
                    print(row[1]+' ', end='')
                    if yf.download(row[1], progress=False).shape[0]:
                        writer.writerow({'Ticker': etf_ticker+row[1], 'Yahoo': row[1], 'Name': row[2]})
                    else:
                        writer.writerow({'Ticker': etf_ticker+row[1], 'Yahoo': '', 'Name': row[2]})
#End rip_tickers


#con = sqlite3.connect('etftrack.db')
rip_tickers('MSGR', [])
print()
