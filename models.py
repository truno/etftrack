from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
#from flask_login import UserMixin
from flask_security import RoleMixin, UserMixin
from flask_admin.contrib import sqla
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.inspection import inspect
#from sql_alchemy import Enum
import pandas as pd
import numpy as np
import pickle

#from etfutil import date_format, adjacent_market_date

db = SQLAlchemy()

class Serializer(object):

    def serialize(self):
        return {c: getattr(self, c) for c in inspect(self).attrs.keys()}

    @staticmethod
    def serialize_list(l):
        return [m.serialize() for m in l]

class UserRole(db.Model):
    __tablename__ = 'usersroles'
    role_id = db.Column(db.ForeignKey('roles.id'), primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), primary_key=True)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    create_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password_hash(self, password):
        return check_password_hash(self.password_hash, password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Role(RoleMixin, db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)
    description = db.Column(db.String(255))

    def __repr__(self):
        return '<Name {}>'.format(self.name) + \
               '<Shares {}>'.format(self.description)

class Snapshot(db.Model, Serializer):
    __tablename__ = 'snapshots'
    add_date = db.Column(db.Date, index=True, primary_key=True)
    fund = db.Column(db.ForeignKey('funds.ticker'), primary_key=True)
    holdings = db.Column(db.PickleType)
    adds = db.Column(db.PickleType)
    drops = db.Column(db.PickleType)
    changes = db.Column(db.PickleType)
    db.UniqueConstraint(add_date, fund)


    def __repr__(self):
        return '<Date {}>'.format(self.add_date) + \
               '<Fund {}>'.format(self.fund_id)

    def serialize(self):
        return {
            "add_date": self.add_date,
            "fund": self.fund,
            "holdings": pickle.loads(self.holdings),
            "adds": pickle.loads(self.adds),
            "drops": pickle.loads(self.drops),
            "changes": pickle.loads(self.changes)
        }

class Holding(db.Model, Serializer):
    __tablename__ = 'holdings'
    add_date = db.Column(db.Date, index=True, primary_key=True)
    fund = db.Column(db.ForeignKey('funds.ticker'), primary_key=True)
    stock = db.Column(db.ForeignKey('stocks.ticker'), primary_key=True)
    created = db.Column(db.DateTime, default=datetime.now)
    name = db.Column(db.String(255))
    shares = db.Column(db.Integer, nullable=False)
    change_pct = db.Column(db.Numeric(precision=7, scale=2))
    db.UniqueConstraint(add_date, fund, stock)

    def __repr__(self):
        return '<Add Date {}>'.format(self.add_date) + \
                '<Created {}'.format(self.created) + \
                '<Fund {}>'.format(self.fund) + \
                '<Stock {}>'.format(self.stock) + \
                '<Name {}>'.format(self.name) + \
                '<Shares {}>'.format(self.shares) + \
                '<Change Pct {}>'.format(self.change_pct)

    def serialize(self):
        return {
            "add_date": self.add_date,
            "created": self.created,
            "fund_id": self.fund_id,
            "stock": self.stock,
            "name": self.name,
            "fund": self.fund,
            "shares": self.shares
        }

class Stock(db.Model, Serializer):
    __tablename__ = 'stocks'
    ticker = db.Column(db.String(16), unique=False, primary_key=True)
    fund = db.Column(db.ForeignKey('funds.ticker'), unique=False, primary_key=True)
    yahoo_ticker = db.Column(db.String(16), nullable=False)
    name = db.Column(db.String(255))
    exchange = db.Column(db.String(16))
    db.UniqueConstraint(fund, ticker)

    def __repr__(self):
        return '<Stock {}>'.format(self.yahoo_ticker)

    def as_dict(self):
        return {s.name: getattr(self, s.name) for s in self.__table__.columns}

    def serialize(self):
        return Serializer.serialize(self)

    def serialize2(self):
        return {
            "id": self.id,
            "fund_ticker": self.ticker,
            "yahoo_ticker": self.yahoo_ticker,
            "name": self.name,
            "exchange": self.exchange,
        }

class Price(db.Model, Serializer):
    __tablename__ = 'prices'
    yahoo_ticker = db.Column(db.String(16), primary_key=True)
    market_date = db.Column(db.Date, index=True, primary_key=True)
    Open = db.Column(db.Float)
    High = db.Column(db.Float)
    Low = db.Column(db.Float)
    Close = db.Column(db.Float)
    Volume = db.Column(db.Float)

    def __repr__(self):
        return '<Date {}>'.format(self.market_date) + \
                '<Yahoo Ticker {}>'.format(self.yahoo_ticker) +\
                '<Open {:.2f}>'.format(self.Open) + \
                '<Close {:.2f}>'.format(self.Close)

    def serialize(self):
        p = Serializer.serialize(self)
        p['market_date'] = p['market_date'].strftime('%Y-%m-%d')
        return p

class Fund(db.Model, Serializer):
    __tablename__ = 'funds'
    ticker = db.Column(db.String(16), nullable=False, primary_key=True)
    name = db.Column(db.String(255))
    has_holdings = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return '<Fund {}>'.format(self.ticker)

    def serialize2(self):
        return Serializer.serialize(self)

    def serialize(self):
        return {
            "ticker": self.ticker,
            "name": self.name,
            "has_holdings": self.has_holdings
        }

    def get_holding_dates(self, reverse_sort=False, last=False, start_date=None, end_date=None):
        if start_date and end_date:
            dates = list(set([h.add_date for h in self.holdings if h.add_date >= datetime.fromisoformat(start_date).date() and h.add_date <= datetime.fromisoformat(end_date).date()]))
        elif start_date:
            dates = list(set([h.add_date for h in self.holdings if h.add_date >= datetime.fromisoformat(start_date).date()]))
        elif end_date:
            dates = list(set([h.add_date for h in self.holdings if h.add_date <= datetime.fromisoformat(end_date).date()]))
        else:
            dates = list(set([h.add_date for h in self.holdings]))
        dates.sort(reverse=reverse_sort)
        if last:
            return dates[0]
        else:
            return dates

    def get_adds(self, last=False, start_date=None, end_date=None):
        dates = self.get_holding_dates(start_date=start_date, end_date=end_date)
        if last and len(dates) > 1:
            dates = dates[-2:]
        elif start_date:
            s_date = datetime.fromisoformat(start_date).date()
            dates = [d for d in dates if d >= s_date]
        all_diffs = {}
        for i in range(len(dates)-1):
            t1 = set([h.stock_id for h in self.holdings if h.add_date == dates[i]])
            t2 = set([h.stock_id for h in self.holdings if h.add_date == dates[i+1]])
            diff = list(t2 - t1)
            if diff:
                all_diffs[dates[i+1]] = diff
        return all_diffs

    def get_drops(self, last=False, start_date=None, end_date=None):
        dates = self.get_holding_dates(start_date=start_date, end_date=end_date)
        if last and len(dates) > 1:
            dates = dates[-2:]
        elif start_date:
            s_date = datetime.fromisoformat(start_date).date()
            dates = [d for d in dates if d >= s_date]
        all_diffs = {}
        for i in range(len(dates)-1):
            t1 = set([h.stock_id for h in self.holdings if h.add_date == dates[i]])
            t2 = set([h.stock_id for h in self.holdings if h.add_date == dates[i+1]])
            diff = list(t1 - t2)
            if diff:
                all_diffs[dates[i+1]] = diff
        return all_diffs

    def get_big_moves(self, threshold=None, last=False, start_date=None, end_date=None):
        dates = self.get_holding_dates(start_date=start_date, end_date=end_date)
        df = pd.DataFrame([{'add_date': h.add_date, 'fund_id': h.fund_id, 'stock_id': h.stock_id, 'name': h.name, 'ticker': h.ticker, 'shares': h.shares} for h in self.holdings if h.add_date in dates])
        if df.empty or len(dates) < 2:
            return {}
        df.sort_values(by='add_date', inplace=True)
        df = df[pd.to_numeric(df['shares'], errors='coerce').notnull()]
        df['pct_change'] = df.groupby('stock_id')['shares'].pct_change()
        df.dropna(inplace=True)
        df = df.astype({'pct_change': float})
        df = df.loc[~(df['pct_change'] == 0.0)]
        df['pct_change'] = df['pct_change'] * 100
        df['pct_change'] = df['pct_change'].round(2)
        if threshold:
            df = df[abs(df['pct_change']) >= threshold]
        if last:
            if reverse_sort:
                dates = dates[:1]
            else:
                dates = dates[-1:]
        changes = dict.fromkeys(dates)
        for index, d in enumerate(dates):
            moves = df[df['add_date'] == d]
            changes.update({d: moves[['stock_id', 'ticker', 'pct_change']].to_dict('records')})
        return changes

    def fund_changes_old(self):
        dates = list(set([h.add_date for h in self.holdings]))
        dates.sort(reverse=True)
        changes = dict.fromkeys(dates)
        for d in dates:
            daily = list(filter(lambda h: h.add_date == d, self.holdings))
            changes.update({d: {'count': len(daily), 'holdings' : [(d.ticker, d.stock_id) for d in daily]}})
        for index, d in enumerate(dates):
            adds = []
            drops = []
            diffs = []
            if index < len(dates) - 1:
                adds = dict.fromkeys(np.setdiff1d([h[1] for h in changes[dates[index]]['holdings']], [h[1] for h in changes[dates[index+1]]['holdings']]))
                for a in adds:
                    adds[a] = [i[0] for i in changes[dates[index]]['holdings'] if i[1] == a][0]
                drops = dict.fromkeys(np.setdiff1d([h[1] for h in changes[dates[index+1]]['holdings']], [h[1] for h in changes[dates[index]]['holdings']]))
                for a in drops:
                    drops[a] = [i[0] for i in changes[dates[index+1]]['holdings'] if i[1] == a][0]
            changes[d].update({'adds': adds})
            changes[d].update({'drops': drops})
        return changes

    def get_adds_drops_big_moves_new(self, threshold=None, last=False, start_date=None, end_date=None):
        dates = self.get_holding_dates(reverse_sort=True, start_date=start_date, end_date=end_date)
        if last:
            dates = dates[:2]
        changes = dict.fromkeys(dates)
        for d in dates:
            daily = list(filter(lambda h: h.add_date == d, self.holdings))
            changes.update({d: {'count': len(daily), 'holdings' : [(d.ticker, d.stock_id) for d in daily]}})
        for index, d in enumerate(dates):
            adds = []
            drops = []
            big_moves = []
            if index < len(dates) - 1:
                adds = dict.fromkeys(np.setdiff1d([h[1] for h in changes[dates[index]]['holdings']], [h[1] for h in changes[dates[index+1]]['holdings']]))
                for a in adds:
                    adds[a] = [i[0] for i in changes[dates[index]]['holdings'] if i[1] == a][0]
                drops = dict.fromkeys(np.setdiff1d([h[1] for h in changes[dates[index+1]]['holdings']], [h[1] for h in changes[dates[index]]['holdings']]))
                for a in drops:
                    drops[a] = [i[0] for i in changes[dates[index+1]]['holdings'] if i[1] == a][0]
            changes[d].update({'adds': adds, 'drops': drops, 'big_moves': []})
        big_moves = self.get_big_moves(threshold=threshold, last=last, reverse_sort=True, start_date=start_date, end_date=end_date)
        bm_dates = big_moves.keys()
        for index, d in enumerate(bm_dates):
            changes[d].update({'big_moves': big_moves[d]})

        if last:
            return changes[dates[0]]
        else:
            return changes

    def get_adds_drops_big_moves(self, threshold=None, last=False, start_date=None, end_date=None):
        dates = self.get_holding_dates(reverse_sort=True, start_date=start_date, end_date=end_date)
        if last:
            dates = dates[:2]
        changes = dict.fromkeys(dates)
        for d in dates:
            daily = list(filter(lambda h: h.add_date == d, self.holdings))
            changes.update({d: {'count': len(daily), 'holdings' : [(d.ticker, d.stock_id) for d in daily]}})
        for index, d in enumerate(dates):
            adds = []
            drops = []
            diffs = []
            if index < len(dates) - 1:
                adds = dict.fromkeys(np.setdiff1d([h[1] for h in changes[dates[index]]['holdings']], [h[1] for h in changes[dates[index+1]]['holdings']]))
                for a in adds:
                    adds[a] = [i[0] for i in changes[dates[index]]['holdings'] if i[1] == a][0]
                drops = dict.fromkeys(np.setdiff1d([h[1] for h in changes[dates[index+1]]['holdings']], [h[1] for h in changes[dates[index]]['holdings']]))
                for a in drops:
                    drops[a] = [i[0] for i in changes[dates[index+1]]['holdings'] if i[1] == a][0]
            changes[d].update({'adds': adds, 'drops': drops, 'big_moves': []})
        big_moves = self.get_big_moves(threshold=threshold, last=last, start_date=start_date, end_date=end_date)
        bm_dates = big_moves.keys()
        for index, d in enumerate(bm_dates):
            changes[d].update({'big_moves': big_moves[d]})

        if last:
            return changes[dates[0]]
        else:
            return changes

    def test_new_holdings_performance(self, indices=['^DJI', '^IXIC', '^GSPC']):
        adds = self.get_adds()
        all_df = pd.DataFrame()
        for add_date, stocks in adds.items():
            #sync market date
            start = adjacent_market_date(adjacent_market_date(add_date, date_format, False))
            end = adjacent_market_date(date.today(), next=False)
            start = start.strftime(date_format)
            end = end.strftime(date_format)
            for stock in stocks:
                df = pd.read_sql(db.session.query(Price)
                                   .filter(Price.stock_id==stock,
                                           Price.market_date>=start,
                                           Price.market_date<=end)
                                    .statement, db.session.bind)
                if df.shape[0]:
                    df['Stock Gain'] = round(df['Close'].pct_change().fillna(0.0)*100, 2)
                    for index in indices:
                        index_stock = Stock.query.filter_by(ticker=index).first()
                        idx_df = pd.read_sql(db.session.query(Price)
                                           .filter(Price.stock_id==index_stock.id,
                                                   Price.market_date>=start,
                                                   Price.market_date<=end)
                                            .statement, db.session.bind)
                        idx_col = index + ' Close'
                        df[idx_col] = round(idx_df['Close'], 2)
                        df[index+' Gain'] = round(df[index+' Close'].pct_change().fillna(0.0)*100, 2)
                        df['Gain to '+index] = df['Stock Gain'] - df[index+' Gain']
                    if all_df.shape[0]:
                        all_df = pd.concat([all_df, df])
                    else:
                        all_df = df
                else:
                    print('\tNo price history for:', stock)

        return all_df
