import numpy as np
import pandas as pd
from gym.utils import seeding
import gym
import heapq
import math as mh
from gym import spaces
import matplotlib
import pdb

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from stable_baselines3.common.vec_env import DummyVecEnv
from tools.qpsolver import qp_solver, qp_SSOA_solver

from warnings import simplefilter
simplefilter(action='ignore', category=FutureWarning)
simplefilter(action='ignore', category=UserWarning)


class SupplierSelectionEnv(gym.Env):
    """A single stock trading environment for OpenAI gym

    Attributes
    ----------
        df: DataFrame
            input data
        stock_dim : int
            number of unique stocks
        hmax : int
            maximum number of shares to trade
        initial_amount : int
            start money
        transaction_cost_pct: float
            transaction cost percentage per trade
        reward_scaling: float
            scaling factor for reward, good for training
        state_space: int
            the dimension of input features
        action_space: int
            equals stock dimension
        tech_indicator_list: list
            a list of technical indicator names
        turbulence_threshold: int
            a threshold to control risk aversion
        day: int
            an increment number to control date

    Methods
    -------
    _sell_stock()
        perform sell action based on the sign of the action
    _buy_stock()
        perform buy action based on the sign of the action
    step()
        at each step the agent will return actions, then
        we will calculate the reward, and return the next observation.
    reset()
        reset the environment
    render()
        use render to return other functions
    save_asset_memory()
        return account value at each time step
    save_action_memory()
        return actions/positions at each time step


    """

    metadata = {"render.modes": ["human"]}

    def __init__(
        self,
        df,
        demanding,
        supplier_num,
        # hmax,
        initial_shortage,
        # transaction_cost_pct,
        reward_scaling,
        state_space,
        action_space,
        # lookback,
        # tech_indicator_list,
        # turbulence_threshold=None,
        # lookback=252,
        day=0,
    ):
        # super(StockEnv, self).__init__()
        # money = 10 , scope = 1
        self.day = day
        # self.lookback = lookback
        self.df = df
        self.demanding = demanding
        self.supplier_num = supplier_num
        # self.hmax = hmax
        self.initial_shortage = initial_shortage
        # self.transaction_cost_pct = transaction_cost_pct
        self.reward_scaling = reward_scaling
        self.state_space = state_space
        self.action_space = action_space
        # self.tech_indicator_list = tech_indicator_list
        # self.agent_num = agent_num

        # action_space normalization and shape is self.stock_dim
        # self.action_space = spaces.Box(low=0, high=self.stock_dim, shape=(self.action_space,))
        self.action_space = spaces.Discrete(self.action_space)

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.state_space, self.supplier_num)
        )


        # load data from a pandas dataframe
        self.data = self.df.loc[self.day, :]
        self.state = np.array(self.data['feature']).T
        # self.last_period_id = 0
        # self.index_value = np.array(self.data['index_list'].values[0])
        self.demand_value = self.demanding[self.day]
        self.price = self.data['price']
        self.quantity = self.data['quantity']
        self.terminal = False
        # self.turbulence_threshold = turbulence_threshold
        # initalize state: inital portfolio return + individual stock return + individual weights
        self.shortage = self.initial_shortage
        self.shortage_gap = [0]

        # memorize portfolio value each step
        self.cost = [0]
        # asset growth ratio: new_portfolio_value / initial_amount
        # self.asset_ratio = [1]
        # memorize portfolio return each step
        self.purchase_quantity_memory = [0]
        self.truth_demand_memory = [0]
        # self.asset_memory = [range(10)]

        self.date_memory = [self.data.index.values[0]]

    def step(self, actions):
        self.terminal = self.day >= len(self.df.index.unique()) - 1
        # print(self.day, self.data['terminal'],actions)
        if self.terminal:
            df = pd.DataFrame(self.purchase_quantity_memory)
            df.columns = ["daily_return"]
            plt.plot(df.daily_return.cumsum(), "r")
            plt.plot(self.purchase_quantity_memory, "r")
            plt.savefig("results/cumulative_reward.png")
            plt.savefig("results/rewards.png")
            plt.close()

            # plt.plot(self.portfolio_return_memory, "r")
            # plt.savefig("results/rewards.png")
            # plt.close()
            print("=================================")
            # print(self.shortage_gap[:5])
            # print(self.purchase_quantity_memory[:5])
            # print(self.truth_demand_memory[:5])
            # print(self.purchase_quantity_memory,self.cost,self.demand_value,len(self.purchase_quantity_memory),len(self.cost))
            print("avevrage cost of decision / period:{}".format(np.log10(np.mean(self.cost))))
            print("shortage gap:{}".format(np.log10(np.sum(self.shortage_gap)/len(self.shortage_gap))))
            print("average unit price:{}".format(np.sum(self.cost) / np.sum(self.purchase_quantity_memory)))
            # df_daily_return = pd.DataFrame(self.portfolio_return_memory)
            # df_daily_return.columns = ["daily_return"]
            # if df_daily_return["daily_return"].std() != 0:
            #     sharpe = (
            #         (252 ** 0.5)
            #         * df_daily_return["daily_return"].mean()
            #         / df_daily_return["daily_return"].std()
            #     )
            #     print("Sharpe: ", sharpe)
            
            # turnover_values = np.sum(np.abs(np.diff(self.weights_memory[1:], axis=0)), axis=1) / np.array(self.weights_memory[1:]).shape[1]

            # Calculate the average turnover rate
            # average_turnover = np.mean(turnover_values)
            # print("Turnover: ", average_turnover)
            print("=================================")

            return self.state, self.reward, self.terminal, {'data_terminal':True}

        else:
            try:
                sol = qp_SSOA_solver(self.price[actions], self.quantity[actions], self.demand_value, lambda_weight=0.9)
            except IndexError:
                pdb.set_trace()
            # print('Exact solution with all time-series')
            # print(sol)
            # weights = np.zeros(self.supplier_num)
            # for k, v in enumerate(actions): weights[v] = sol['x'][k]
            # self.actions_memory.append(actions)
            # self.weights_memory.append(weights)
            # data_terminal = 0 if self.current_period_id > self.last_period_id else 1
            data_terminal = np.array(self.data['terminal'])
            # calculate portfolio return
            # individual stocks' return * weight
            # Week_ID = self.data.index.values[0]
            total_quantity = sum(sol)
            truth_demanding = self.demand_value

            # update portfolio value
            # self.daily_return_memory.append(total_quantity)
            # new_portfolio_value = self.portfolio_value * (1 + np.sum(total_quantity))
            # self.portfolio_value = new_portfolio_value if new_portfolio_value > 0 else 0

            # save into memory
            self.purchase_quantity_memory.append(total_quantity)
            self.truth_demand_memory.append(truth_demanding)
            
            # self.asset_memory.append(self.demand_value)
            # self.asset_ratio.append(round(new_portfolio_value/self.asset_memory[-2],5))
            # print(truth_demanding,total_quantity)
            self.shortage_gap.append(truth_demanding - total_quantity) 

            # self.tracking_error = [truth_indexing - portfolio_return]
            # jacarrd similarity
            # sim = len(set(self.actions_memory[-1]).intersection(set(self.actions_memory[-2]))) / \
            #       len(set(self.actions_memory[-1]).union(set(self.actions_memory[-2])))
            # print(self.demand_value, total_quantity)
            cost = sum(sol * self.price[actions])
            gap = np.absolute(np.mean(abs(self.demand_value - total_quantity)))
            self.reward = (1 - np.clip(gap/2000,0,1)**(3/4))**(4/3) + (1 - np.clip(cost/50000,0,1)**(3/4))**(4/3)
            # self.reward = -np.log(cost + 0.0001) + 13
            # print(self.reward, self.reward+15,gap, cost)
            self.cost.append(cost)
            # load next state
            self.day += 1
            self.data = self.df.loc[self.day, :]
            self.state = np.array(self.data['feature']).T
            self.price = self.data['price']
            self.quantity = self.data['quantity']
            # self.last_period_id = self.current_period_id
            # self.current_period_id = np.array(self.data['period_id'])
            # self.index_value = np.array(self.data['index_list'].values[0])
            self.demand_value = self.demanding[self.day]
            self.date_memory.append(self.data.index.values[0])

        return self.state, self.reward, self.terminal, {'data_terminal':data_terminal}

    def reset(self):
        self.asset_memory = [self.initial_shortage]
        self.day = 0
        self.data = self.df.loc[self.day, :]
        # load states
        self.state = np.array(self.data['feature']).T
        self.price = self.data['price']
        self.quantity = self.data['quantity']
        # self.last_period_id = 0
        # self.current_period_id = np.array(self.data['period_id'])
        self.initial_shortage = self.initial_shortage
        self.terminal = False
        self.purchase_quantity_memory = [0]
        self.truth_demand_memory = [0]
        self.cost = [0]
        # self.actions_memory = [[1 / self.stock_dim] * self.stock_dim]
        self.actions_memory = [range(10)]
        self.weights_memory = [range(self.supplier_num)]
        self.daily_return_memory = [range(10)]
        self.date_memory = [self.data.index.values[0]]
        self.shortage_gap = [0]
        return self.state

    def render(self, mode="human"):
        return self.state

    def softmax_normalization(self, actions):
        # cpy_action = deepcopy(actions)
        # max_number = heapq.nlargest(10, cpy_action) 
        # max_index = []
        # for t in max_number:
        #     index = cpy_action.index(t)
        #     max_index.append(index)
        #     cpy_action[index] = 0
        # actions = [0 if i not in max_index else actions[i] for i in len(actions)]
        numerator = np.exp(actions)
        denominator = np.sum(np.exp(actions))
        softmax_output = numerator / denominator
        return softmax_output

    def save_asset_memory(self):
        date_list = self.date_memory
        portfolio_return = self.purchase_quantity_memory
        df_account_value = pd.DataFrame(
            {"date": date_list, "daily_return": portfolio_return}
        )
        return df_account_value

    def save_truth_asset_memory(self):
        date_list = self.date_memory
        portfolio_return = self.truth_demand_memory
        df_truth_value = pd.DataFrame(
            {"date": date_list, "daily_return": portfolio_return}
        )
        return df_truth_value

    def save_tracking_error_memory(self):
        date_list = self.date_memory
        shortage_gap = self.shortage_gap
        df_error_value = pd.DataFrame(
            {"date": date_list, "daily_return": shortage_gap}
        )
        return df_error_value

    def save_daily_return_memory(self):
        date_list = self.date_memory
        df_date = pd.DataFrame(date_list)
        df_date.columns = ["date"]
        return_list = self.daily_return_memory
        # df_days_return = pd.DataFrame(
        #     {"date":df_date,"daily_return":return_list}
        #     )
        # print(df_days_return)
        # exit()
        df_days_return = pd.DataFrame(return_list)
        # df_days_return.index = df_date.date
        return df_days_return

    def save_action_memory(self):
        # date and close price length must match actions length
        date_list = self.date_memory
        df_date = pd.DataFrame(date_list)
        df_date.columns = ["date"]

        action_list = self.actions_memory
        df_actions = pd.DataFrame(action_list)
        # df_actions.columns = self.data.tic.values
        df_actions.index = df_date.date
        return df_actions

    def _seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def get_sb_env(self):
        e = DummyVecEnv([lambda: self])
        state = e.reset()
        return e, state
