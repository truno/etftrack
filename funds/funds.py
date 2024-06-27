from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, jsonify
)
from flask_login import current_user, login_user, logout_user, login_required
from models import Fund, Stock, Holding, Price, Snapshot, db
from sqlalchemy import func, desc
import numpy as np
import pandas_market_calendars as mcal
import etfutil as eu
import datetime

nyse = mcal.get_calendar('NYSE')
funds_bp = Blueprint('funds', __name__, template_folder='templates')

@funds_bp.route('/view')
#@login_required
def view():
    funds = Fund.query.order_by("ticker").all()
#    holdings = Holding.query.all()
#    stocks = Stock.query.all()
    return render_template('funds/view.html', title='Funds', funds=funds)

@funds_bp.route('/snapshots')
#@login_required
def snapshots():
    funds = Fund.query.order_by("ticker").all()
    snapshots = []
    for f in funds:
        snapshot = Snapshot.query.filter_by(fund=f.ticker).order_by(desc('add_date')).first().serialize()
        snapshot['fund'] = f.ticker
        snapshot['changes_count'] = len(snapshot['changes'])
        snapshots.append(snapshot)
    return render_template('funds/snapshots.html', title='Funds', snapshots=snapshots)

@funds_bp.route('/last_changes')
#@login_required
def last_changes():
    funds = Fund.query.order_by("ticker").all()
    changes = []
    for f in fund:
        changes.append({"ticker": f.ticker})
    for c in changes:
        d = f.get_holding_dates(reverse_sort=True, last=True)
        c.append({"ticker": f.ticker}.update(f.get_adds_drops_big_moves(threshold=1.0, last=True, end_date=d.strftime('%Y-%m-%d'))))
    return render_template('funds/view.html', title='Funds', funds=funds)

@funds_bp.route('/fund/<string:ticker>/')
#@login_required
def display_fund(ticker):
    fund = Fund.query.filter_by(ticker=ticker).first()
    snapshots = Snapshot.query.filter_by(fund=ticker).order_by(desc('add_date')).all()
    return render_template('funds/fund.html', title=fund.name, ticker=ticker,
                            fund=fund.serialize(),
                            snapshots=[s.serialize() for s in snapshots])

@funds_bp.route('/stock/<string:fund>/<string:ticker>/edit', methods=['GET', 'POST'])
def edit_stock(fund, ticker):
    stock = Stock.query.filter_by(fund=fund, ticker=ticker).first()
    if request.method == 'POST':
        if stock:
            db.session.delete(stock)
            db.session.commit()

            fund = request.form['fund']
            ticker = request.form['ticker']
            yahoo_ticker = request.form['yahoo_ticker']
            name = request.form['name']
            stock = Stock(fund=fund, ticker=ticker,
                          yahoo_ticker=yahoo_ticker, name=name)

            db.session.add(stock)
            db.session.commit()
            return redirect(f'/empty_stocks')
        return f"Stock with fund = {fund} and ticker={ticker} Does not exist"

    return render_template('stocks/edit_stock.html', stock = stock)

@funds_bp.route('/stock/<string:fund_ticker>/<string:stock_ticker>/')
@funds_bp.route('/stock/<string:fund_ticker>/<string:stock_ticker>/<string:action>/<string:date>')
@funds_bp.route('/stock/<string:fund_ticker>/<string:stock_ticker>/<string:action>/<string:date>/<string:pct_change>')
#@login_required
def display_stock(fund_ticker, stock_ticker, action=None, date=None, pct_change=None):
    fund = Fund.query.filter_by(ticker=fund_ticker).first()
    stock = Stock.query.filter_by(fund=fund.ticker, ticker=stock_ticker).first()
    prices = Price.query.filter_by(yahoo_ticker=stock.yahoo_ticker).all()
    if date:
#        valid_days = nyse.valid_days(start_date='2022-04-22', end_date=date)
        if action == 'Add' or action == 'Big Move':
            action_date = date
#            holding = Holding.query.filter_by(yahoo_ticker=stock.yahoo_ticker, add_date=action_date).first()
            holding = Holding.query.filter_by(fund=fund.ticker, stock=stock.ticker, add_date=action_date).first()
            print("Holding:", holding, type(holding.add_date))
            ohlcv = Price.query.filter_by(yahoo_ticker=stock.yahoo_ticker, market_date=action_date).first()
        elif action == 'Drop':
#            action_date = str(valid_days[-2]).split()[0]
            holding = Holding.query.filter_by(fund=fund.ticker, stock=stock.ticker).all()[-1]
            ohlcv = Price.query.filter_by(yahoo_ticker=stock.yahoo_ticker, market_date=holding.add_date).first()
            action_date = holding.add_date.strftime('%Y-%m-%d')
        prices = [p for p in prices if p.market_date > (holding.add_date - datetime.timedelta(days=50))]
    
    return render_template('stocks/stock.html', title=stock.name,
                            stock=stock, prices=[p.serialize() for p in prices],
#                            date=date, holding=holding, ohlcv=ohlcv,
                            date=datetime.date.fromisoformat(action_date),
                            action=action, fund=fund, holding=holding,
                            ohlcv=ohlcv, pct_change=pct_change)

@funds_bp.route('/fund/create', methods = ['GET', 'POST'])
def create():
    if request.method == 'GET':
        return render_template('funds/createfund.html')

    if request.method == 'POST':
        fund = Fund(ticker=request.form['ticker'], name=request.form['name'])
        db.session.add(fund)
        db.session.commit()
        return redirect('/view')
