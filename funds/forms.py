from flask_wtf import FlaskFrom
from wtforms import SelectMultipleField, SubmitField

class SelectFundsForm(FlaskForm):
    fund_list = SelectMultipleField("Funds")
    follow_list = SelectMultipleField("Followed Funds")
    submit('Save')
