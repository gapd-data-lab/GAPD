import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
import plotly.graph_objs as go
import seaborn as sns
from scipy.stats import norm
import requests
import re
import streamlit as st
import yfinance as yf

class BlackScholes:
    def __init__(self, r, s, k, t, sigma):
        self.r = r          # Risk-free rate
        self.k = k          # Strike price
        self.s = s          # Stock price
        self.t = t          # Time to expiration
        self.sigma = sigma  # Volatility

    def calculate_df(self):
        try:
            d1 = (np.log(self.s / self.k) + (self.r + 0.5 * self.sigma**2) * self.t) / (self.sigma * np.sqrt(self.t))
            d2 = d1 - self.sigma * np.sqrt(self.t)
            return d1, d2
        except ZeroDivisionError:
            raise ValueError("Enter time value greater than 0")

    def option(self, option_type='Call'):
        d1, d2 = self.calculate_df()
        option_type = option_type.capitalize()
        try:
            if option_type == "Call":
                price = (self.s * norm.cdf(d1)) - (self.k * np.exp(-self.r * self.t) * norm.cdf(d2))
            elif option_type == "Put":
                price = (self.k * np.exp(-self.r * self.t) * norm.cdf(-d2)) - (self.s * norm.cdf(-d1))
            else:
                raise ValueError('Invalid input. Please enter "Call" or "Put"')

            return round(price, 2)
        except Exception as e:
            raise RuntimeError(f"Error calculating option price: {e}")

    def greeks(self, option_type):
        d1, d2 = self.calculate_df()
    
        try:
            pdf_d1 = norm.pdf(d1)
            cdf_d1 = norm.cdf(d1)
            cdf_neg_d1 = norm.cdf(-d1)
            cdf_d2 = norm.cdf(d2)
            cdf_neg_d2 = norm.cdf(-d2)
            sqrt_T = np.sqrt(self.t)
            exp_neg_rt = np.exp(-self.r * self.t)

            gamma = pdf_d1 / (self.s * self.sigma * sqrt_T)
            vega = self.s * pdf_d1 * sqrt_T 
            if option_type == "Call":
                delta = cdf_d1
                theta = (-self.s * pdf_d1 * self.sigma / (2 * sqrt_T)) - (self.r * self.k * exp_neg_rt * cdf_d2)
                rho = self.k * self.t * exp_neg_rt * cdf_d2
            elif option_type == "Put":
                delta = -cdf_neg_d1
                theta = (-self.s * pdf_d1 * self.sigma / (2 * sqrt_T)) + (self.r * self.k * exp_neg_rt * cdf_neg_d2)
                rho = -self.k * self.t * exp_neg_rt * cdf_neg_d2
            else:
                raise ValueError("Invalid option type. Must be 'Call' or 'Put'.")
            
            # Secondary Greeks
            vanna = vega * (1 - d1 / (self.sigma * sqrt_T))
            vomma = vega * d1 * d2 / self.sigma
            charm = -pdf_d1 * (2 * (self.r - 0.5 * self.sigma**2) * self.t - d2 * self.sigma * sqrt_T) / (2 * sqrt_T)
            zomma = vega * (d1 * d2 - 1) / self.sigma
        
            return {
                'delta': round(delta, 3),
                'gamma': round(gamma, 6),
                'theta': round(theta / 365, 6),  # Convert theta to per-day format
                'vega': round(vega * 0.01, 6),  # Vega is multiplied by 0.01 to adjust for percentage format
                'rho': round(rho * 0.01, 6),     # Rho in percentage format
                'vanna': round(vanna, 6),
                'vomma': round(vomma, 6),
                'charm': round(charm, 6),
                'zomma': round(zomma, 6)
                }

        except ZeroDivisionError:
            return "Error: Division by zero encountered in Greek calculations."
        except ValueError as e:
            return f"Error: {e}"

    def greek_visualisation(self, option_type, greek):
        fig = go.Figure()
    
        line_color = '#FA7070' if option_type == 'Call' else '#799351'
        min_s = self.s * 0.92
        max_s = self.s * 1.09
        spot_values = np.linspace(min_s, max_s, 200)

        greek_values = [BlackScholes(self.r, s, self.k, self.t, self.sigma).greeks(option_type)[greek] for s in spot_values]
        current_greek_value = BlackScholes(self.r, self.s, self.k, self.t, self.sigma).greeks(option_type)[greek]
        fig.add_trace(go.Scatter(x=spot_values, y=greek_values, mode='lines', name=greek.capitalize(), line=dict(color=line_color, width=3)))
        fig.add_trace(go.Scatter(x=[self.s], y=[current_greek_value], mode='markers', name=f'Current {greek.capitalize()}', marker=dict(color='Yellow', size=7)))
        fig.update_layout(title=f'{greek.capitalize()} vs Spot Price ({option_type})', xaxis_title='Spot Price', yaxis_title=greek.capitalize())
        
        return fig

    def monte_carlo_pricing(self, num_simulations=10000):
        Z = np.random.standard_normal(num_simulations)
        ST = self.s * np.exp((self.r - 0.5 * self.sigma**2) * self.t + self.sigma * np.sqrt(self.t) * Z)
        payoffs = np.maximum(ST - self.k, 0)  # Call options
        option_price = np.exp(-self.r * self.t) * np.mean(payoffs)
        return round(option_price,2)

    def american_option_pricing(self, s, k, t, r, n, sigma, option_type='call'):
        n = int(n)
        dt = t / n
        u = np.exp(sigma * np.sqrt(dt)) 
        d = 1 / u                       
        p = (np.exp(r * dt) - d) / (u - d)  

        stock_price = np.zeros((n + 1, n + 1))
        option_value = np.zeros((n + 1, n + 1))

        for i in range(n + 1):
            stock_price[i, n] = s * (u ** i) * (d ** (n - i))

        if option_type == 'call':
            for i in range(n + 1):
                option_value[i, n] = max(0, stock_price[i, n] - k)
        elif option_type == 'put':
            for i in range(n + 1):
                option_value[i, n] = max(0, k - stock_price[i, n])
        else:
            raise ValueError("option_type should be 'call' or 'put'")
    
        for j in range(n - 1, -1, -1):
            for i in range(j + 1):
                option_value[i, j] = np.exp(-r * dt) * (p * option_value[i, j + 1] + (1 - p) * option_value[i + 1, j + 1])
           
                if option_type == 'call':
                    option_value[i, j] = max(option_value[i, j], stock_price[i, j] - k)
                elif option_type == 'put':
                    option_value[i, j] = max(option_value[i, j], k - stock_price[i, j])
            
                stock_price[i, j] = stock_price[i, j + 1] * d

        return option_value[0, 0]



def monte_carlo_pricing_visualization(option_value, strike_price, time_to_expiry, volatility, risk_free_rate, num_simulations=1000, num_steps=252):
    dt = time_to_expiry / num_steps
    asset_paths = np.zeros((num_steps, num_simulations))
    asset_paths[0] = option_value

    for t in range(1, num_steps):
        rand = np.random.standard_normal(num_simulations)
        asset_paths[t] = asset_paths[t - 1] * np.exp((risk_free_rate - 0.5 * volatility ** 2) * dt + volatility * np.sqrt(dt) * rand)

    fig = go.Figure()
    
    for i in range(num_simulations):
        fig.add_trace(go.Scatter(x=np.linspace(0, time_to_expiry, num_steps), y=asset_paths[:, i], mode='lines', line=dict(width=1)))
    
    fig.update_layout(title="Asset Price Paths", xaxis_title="Time (Years)", yaxis_title="Asset Price", showlegend=False)

    return fig


def binomial_pricing_visualization(spot_price, strike_price, time_to_expiry, volatility, risk_free_rate, num_steps, option_type='Call'):
    dt = time_to_expiry / num_steps  
    u = np.exp(volatility * np.sqrt(dt))
    d = 1 / u 
    p = (np.exp(risk_free_rate * dt) - d) / (u - d)  

    asset_prices = np.zeros((num_steps + 1, num_steps + 1))

    for i in range(num_steps + 1):
        for j in range(i + 1):
            asset_prices[j, i] = spot_price * (u ** (i - j)) * (d ** j)

    fig = go.Figure()

    for i in range(num_steps + 1):
        for j in range(i + 1):
            fig.add_trace(go.Scatter(x=[i], y=[asset_prices[j, i]],mode='markers+text',marker=dict(size=10, color='blue'),text=f"{asset_prices[j, i]:.2f}",textposition='top center',showlegend=False))

    for i in range(num_steps):
        for j in range(i + 1):
            fig.add_trace(go.Scatter(x=[i, i + 1], y=[asset_prices[j, i], asset_prices[j, i + 1]],mode='lines', line=dict(color='gray', dash='dash'),showlegend=False))
            fig.add_trace(go.Scatter(x=[i, i + 1], y=[asset_prices[j, i], asset_prices[j + 1, i + 1]],mode='lines', line=dict(color='gray', dash='dash'),showlegend=False))
    fig.update_layout(title=f"Binomial Tree for {option_type} Option Pricing",xaxis_title="Step",yaxis_title="Asset Price",xaxis=dict(tickmode='linear', tick0=0, dtick=1),yaxis=dict(tickmode='linear'),showlegend=False,height=600,width=800)
 
    return fig

def fetch_data(selected_index):
    try:
        nifty_latest = yf.download(selected_index, interval = '1m', period = '1d')
        nifty_latest = round(nifty_latest.Close.iloc[-1], 1)
        return nifty_latest
    except:
        return ["No Price available"] 
    
def fetch_expiry_dates(selected_index):
    """Fetches expiry dates for the selected index if available."""
    try:
        ticker = yf.Ticker(selected_index)
        options = ticker.options
        if options:
            return options
        else:
            return ["No options available"]
    except Exception as e:
        st.sidebar.write(f"Error fetching options for {selected_index}: {e}")
        return ["Error fetching options"]

def calculate_time_to_expiry(expiration_date):
    """Calculates time to expiry in years from today's date to the expiration date."""
    today = datetime.now().date()
    expiry_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()
    days_to_expiry = (expiry_date - today).days
    return days_to_expiry / 252.0


def get_option_strike_prices(ticker):
    stock = yf.Ticker(ticker)
    expirations = stock.options
    strike_prices = {}

    for expiration in expirations:
        try:
            options_chain = stock.option_chain(expiration)
            if 'calls' in options_chain._fields and 'puts' in options_chain._fields:
                call_strikes = options_chain.calls['strike'].tolist()
                put_strikes = options_chain.puts['strike'].tolist()
                strike_prices[expiration] = {
                    'calls': call_strikes,
                    'puts': put_strikes
                }
            else:
                strike_prices[expiration] = {
                    'calls': [],
                    'puts': []
                }
        except Exception as e:
            st.sidebar.write(f"Error fetching options for {expiration}: {e}")

    return strike_prices




def main():
    indices_names = {'AAPL': 'Apple Inc.', 'NVDA': 'NVIDIA Corporation', '^RUT': 'Russell 2000 Index', '^VIX': 'CBOE Volatility Index (VIX)',
        'IWM': 'iShares Russell 2000 ETF', 'TSLA': 'Tesla, Inc.', 'QQQ': 'Invesco QQQ Trust', '^SPX': 'S&P 500 Index'}

    st.sidebar.header("Select an Index")
    selected_index = st.sidebar.selectbox(
        "Select an underlying asset", 
        options=list(indices_names.keys()), 
        key='underlying_asset'
    )
    st.sidebar.write(f"Selected asset: **{indices_names[selected_index]}**")

    # Fetching and displaying available expirations for the selected index
    expirations = fetch_expiry_dates(selected_index)
    expiration_date = st.sidebar.selectbox(
        "Select Expiration Date", 
        options=expirations, 
        key='expiration_date'
    )
    
    st.sidebar.write(f"Selected expiration: **{expiration_date}**")

    # Fetching the current price for the selected index
    # nifty_price = fetch_data(selected_index)
    # nifty_price = float(nifty_price.iloc[-1]) if isinstance(nifty_price, pd.Series) and not nifty_price.empty else None
    # if nifty_price is not None:
    #     # Proceed with calculations if nifty_price is valid
    #     strike_prices_data = get_option_strike_prices(selected_index)
    #     expiration_dates = list(strike_prices_data.keys())
    
    #     # Safeguard to check call_strikes is not empty
    #     call_strikes = strike_prices_data.get(expiration_date, {}).get('calls', [])
    #     if call_strikes:
    #         closest_strike = min(call_strikes, key=lambda x: abs(float(x) - nifty_price))

    # # Fetch available expirations and strike prices
    # # strike_prices_data = get_option_strike_prices(selected_index)
    # # expiration_dates = list(strike_prices_data.keys())
    


    # # Get strike prices for the selected expiration
    # # call_strikes = strike_prices_data[expiration_date]['calls']
    
    # # Find the closest strike price to the current stock price
    # # call_strikes = list(call_strikes) if isinstance(call_strikes, pd.Series) else call_strikes
    # # closest_strike = min(call_strikes, key=lambda x: abs(float(x) - nifty_price))

    
    # # Create a select box to allow users to choose a strike price
    # selected_strike = st.sidebar.selectbox(
    #     "Select Strike Price (Closest to Spot Price)", 
    #     options=sorted(call_strikes), 
    #     index=call_strikes.index(closest_strike), 
    #     key='strike_price'
    # )
    
    # st.sidebar.write(f"Selected strike price: **{selected_strike:.2f}**")

    # Fetching the current price for the selected index
    nifty_price = fetch_data(selected_index)
    if nifty_price is not None:
        # Se for uma Series (com um único elemento), use .iloc[0] para extrair o valor
        if hasattr(nifty_price, "iloc"):
            nifty_price = float(nifty_price.iloc[0])
        else:
            nifty_price = float(nifty_price)
    else:
        nifty_price = None
    if nifty_price:
        # Fetch available expirations and strike prices
        strike_prices_data = get_option_strike_prices(selected_index)
        
        # Ensure expiration date and call strikes are valid before proceeding
        if expiration_date in strike_prices_data:
            call_strikes = strike_prices_data.get(expiration_date, {}).get('calls', [])
            
            if call_strikes:
                closest_strike = min(call_strikes, key=lambda x: abs(float(x) - nifty_price))
            else:
                st.write("No call strikes available for the selected expiration date.")
                return  # Exit if no strike prices are available
        else:
            st.write("Invalid expiration date or no data available.")
            return

        # Proceed only if `call_strikes` contains valid data
        selected_strike = st.sidebar.selectbox(
            "Select Strike Price (Closest to Spot Price)", 
            options=sorted(call_strikes), 
            index=call_strikes.index(closest_strike) if call_strikes else 0
        )
        
        st.sidebar.write(f"Selected strike price: **{selected_strike:.2f}**")


    # Now, you can proceed with further calculations using the selected strike price
    st.title("Option Pricing Simulation")
    st.write(f"Simulating for **{indices_names[selected_index]}** with strike price **{selected_strike}** and expiration **{expiration_date}**.")


    strike_price = selected_strike
    time_to_expiry = calculate_time_to_expiry(expiration_date)
    option_type = 'Call'
    spot_price = nifty_price
    volatility = 20.0
    risk_free_rate = 5.0
    num_steps=10.0

    option = st.sidebar.selectbox("Pick a strategy", ['Black Scholes Pricing', 'Monte Carlo Simulation', 'Binomial Tree Forecasting'], key='option_strategy')

    if option == 'Black Scholes Pricing':
        st.title("Black-Scholes Option Pricing and Greek Visualizations")
        st.sidebar.header("Inputs")
        spot_price = st.sidebar.number_input('Stock Price', min_value=1.0, max_value=40000.0, value=nifty_price, step=5.0, key='spot_price')
        # strike_price = st.sidebar.number_input("Strike Price", value=selected_strike, min_value=1.0, max_value=40000.0, key='selected_strike')
        # st.sidebar.write(f"Time to expiration in Days : **{int(round(time_to_expiry * 252,2)) }**")
        time_to_expiry_val = st.sidebar.number_input("Time to Expiry (Days)", value=int(round(time_to_expiry * 252,2)), key='time_to_expiry')
        time_to_expiry=time_to_expiry_val/252
        option_type = st.selectbox("Option Type", ['Call', 'Put'], key='option_type')
        volatility = st.sidebar.number_input('Volatility (%)', min_value=1.0, max_value=100.0, value=20.0, step=0.5, key='volatility')
        risk_free_rate = st.sidebar.number_input('Risk Free Rate (%)', min_value=0.0, max_value=20.0, value=5.0, step=0.1, key='risk_free_rate')
        # volatility = st.sidebar.slider('Volatility (%)', min_value=1.0, max_value=100.0, value=20.0, step=0.5, key='volatility')
        # risk_free_rate = st.sidebar.slider('Risk Free Rate (%)', min_value=0.0, max_value=20.0, value=5.0, step=0.1, key='risk_free_rate')
        
        st.sidebar.header("Inputs for Black Scholes")
        bs_model = BlackScholes(r=risk_free_rate / 100, s=spot_price, k=strike_price, t=time_to_expiry, sigma=volatility / 100)
        option_price = bs_model.option(option_type)
        
        st.subheader("Greek Visualizations")

        # if st.sidebar.button("Run"): 
        #     st.sidebar.write(f"Option Price: {option_price}")
        #     greek_types = ['delta', 'gamma', 'theta', 'vega', 'rho', 'vanna', 'vomma', 'charm', 'zomma']  # Added secondary Greeks here
        #     for greek in greek_types:
        #         fig = bs_model.greek_visualisation(option_type, greek)
        #         st.plotly_chart(fig)

# Main logic for visualization in rows of two columns
        if st.sidebar.button("Run"):
            st.sidebar.write(f"Option Price: {option_price}")
    
    # Visualize Delta and Gamma in the first row
            col1, col2 = st.columns(2)
            with col1:
                delta_fig = bs_model.greek_visualisation(option_type, 'delta')
                st.plotly_chart(delta_fig)
            with col2:
                gamma_fig = bs_model.greek_visualisation(option_type, 'gamma')
                st.plotly_chart(gamma_fig)

    # Visualize Theta and Vega in the second row
            col3, col4 = st.columns(2)
            with col3:
                theta_fig = bs_model.greek_visualisation(option_type, 'theta')
                st.plotly_chart(theta_fig)
            with col4:
                vega_fig = bs_model.greek_visualisation(option_type, 'vega')
                st.plotly_chart(vega_fig)

    # Visualize Rho and Vanna in the third row
            col5, col6 = st.columns(2)
            with col5:
                rho_fig = bs_model.greek_visualisation(option_type, 'rho')
                st.plotly_chart(rho_fig)
            with col6:
                vanna_fig = bs_model.greek_visualisation(option_type, 'vanna')
                st.plotly_chart(vanna_fig)

    # Visualize Vomma and Charm in the fourth row
            col7, col8 = st.columns(2)
            with col7:
                vomma_fig = bs_model.greek_visualisation(option_type, 'vomma')
                st.plotly_chart(vomma_fig)
            with col8:
                charm_fig = bs_model.greek_visualisation(option_type, 'charm')
                st.plotly_chart(charm_fig)

    # Visualize Zomma in the fifth row (it has no pair in this case)
            col9, _ = st.columns(2)
            with col9:
                zomma_fig = bs_model.greek_visualisation(option_type, 'zomma')
                st.plotly_chart(zomma_fig)

    elif option == 'Monte Carlo Simulation':
        st.title("Monte Carlo Simulation Option Pricing and Simulating Asset prices")
        st.sidebar.header("Inputs")
        num_steps = st.sidebar.number_input("Number of Steps", value=252, min_value=1, key='num_steps_mc')
        num_simulations = st.sidebar.number_input("Number of Simulations", value=1000, min_value=500, max_value=2000, step=100, key='num_simulations')
        spot_price = st.sidebar.number_input('Stock Price', min_value=1.0, max_value=40000.0, value=nifty_price, step=5.0, key='spot_price')
        # strike_price = st.sidebar.number_input("Strike Price", value=selected_strike, min_value=1.0, max_value=40000.0, key='selected_strike')
        # st.sidebar.write(f"Time to expiration in Days : **{int(round(time_to_expiry * 252,2)) }**")
        time_to_expiry_val = st.sidebar.number_input("Time to Expiry (Days)", value=int(round(time_to_expiry * 365,2)), key='time_to_expiry')
        time_to_expiry=time_to_expiry_val/252
        volatility = st.sidebar.number_input('Volatility (%)', min_value=1.0, max_value=100.0, value=20.0, step=0.5, key='volatility')
        risk_free_rate = st.sidebar.number_input('Risk Free Rate (%)', min_value=0.0, max_value=20.0, value=5.0, step=0.1, key='risk_free_rate')
        # volatility = st.sidebar.slider('Volatility (%)', min_value=1.0, max_value=100.0, value=20.0, step=0.5, key='volatility')
        # risk_free_rate = st.sidebar.slider('Risk Free Rate (%)', min_value=0.0, max_value=20.0, value=5.0, step=0.1, key='risk_free_rate')
        bs_model = BlackScholes(r=risk_free_rate / 100, s=spot_price, k=strike_price, t=time_to_expiry, sigma=volatility / 100)
        monte_carlo_price = bs_model.monte_carlo_pricing(num_simulations=int(num_simulations))
        if st.sidebar.button("Run"):
            st.sidebar.write(f"Monte Carlo Option Price: {monte_carlo_price}")
            simulation_fig = monte_carlo_pricing_visualization(spot_price, strike_price, time_to_expiry, volatility / 100, risk_free_rate / 100, num_simulations, int(num_steps))
            st.plotly_chart(simulation_fig)
            
    else:
        st.sidebar.header("Inputs")
        st.title("Binomial Option Pricing and Forecasting Asset Prices")

        # option_type = st.selectbox("Option Type", ['Call', 'Put'], key='option_type')
        spot_price = st.sidebar.number_input("Stock Price", min_value=0.0, max_value=40000.0, value=nifty_price, step=5.0)
        # strike_price = st.sidebar.number_input("Strike Price", value=selected_strike, min_value=1.0, max_value=40000.0, key='selected_strike')
        # st.sidebar.write(f"Time to expiration in Days : **{int(round(time_to_expiry * 365,2)) }**")
        time_to_expiry_val = st.sidebar.number_input("Time to Expiry (Days)", value=int(round(time_to_expiry * 252,2)), key='time_to_expiry')
        time_to_expiry=time_to_expiry_val/252
        volatility = st.sidebar.number_input("Volatility (%)", min_value=0.0, max_value=100.0, value=20.0) / 100
        risk_free_rate = st.sidebar.number_input("Risk Free Rate (%)", min_value=0.0, max_value=20.0, value=5.0) / 100
        # volatility = st.sidebar.slider('Volatility (%)', min_value=1.0, max_value=100.0, value=1.0, step=0.5, key='volatility')
        # risk_free_rate = st.sidebar.slider('Risk Free Rate (%)', min_value=0.0, max_value=20.0, value=5.0, step=0.1, key='risk_free_rate')
        num_steps = st.sidebar.number_input("Number of Steps", value=10, min_value=10, max_value=50, step=10)

        bs = BlackScholes(risk_free_rate, spot_price, strike_price, time_to_expiry, volatility)

        option_price = bs.american_option_pricing(spot_price, strike_price, time_to_expiry, risk_free_rate, num_steps, volatility, option_type.lower())

        if st.sidebar.button('Run'):
            st.sidebar.write(f"The calculated option value is: **{option_price:.2f}**")
            binomial_tree_fig = binomial_pricing_visualization(spot_price, strike_price, time_to_expiry, volatility, risk_free_rate, num_steps, option_type)
            st.plotly_chart(binomial_tree_fig)

if __name__ == "__main__":
    main()

st.sidebar.text("")
st.sidebar.text("")
st.sidebar.text("")
st.sidebar.text("")
col1, col2 = st.sidebar.columns(2)
col1.text("Linkedin:")
col1.page_link("https://www.linkedin.com/in/kushalgowdagv/",label="Kushal Gowda")
