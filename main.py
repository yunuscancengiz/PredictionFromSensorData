from src._create_dataset import DatasetCreator
from src.producer import SimpleProducer
from src.data_processor import DataPreprocessor
from src.druid_data import DruidDataFetcher
from src.model import RNNModel
from src.postgre_db import PostgreClient
from src.consumer import SimpleConsumer
from src._logger import ProjectLogger
import time as t
from datetime import datetime, timedelta, time
import threading
import traceback


class RunPipeline:
    logger = ProjectLogger(class_name='RunPipeline').create_logger()


    def __init__(self):
        self.lstm_model = RNNModel()
        self.dataset_creator = DatasetCreator()
        self.producer = SimpleProducer()
        self.druid_fetcher = DruidDataFetcher()
        self.preprocesser = DataPreprocessor()
        self.postgre_client = PostgreClient()

        # create postgre tables
        self.postgre_client.create_table(table_name='model_results_1m')
        self.postgre_client.create_table(table_name='model_results_15m')

        self.consumers = []
        self.starting_date_1m = None
        self.starting_date_15m = None

        self.starting_hour = 0
        self.starting_minute = 0


    def run(self):
        self.start_consumers()
        starting_time = datetime.combine(datetime.now().date(), time(self.starting_hour, self.starting_minute)).replace(second=0, microsecond=0)
        self.logger.info(msg=f'The program will start at {starting_time}.')
        while True:
            try:
                now = datetime.now()
                if now.hour == self.starting_hour and now.minute == self.starting_minute:
                    self.pipeline()

                    # sleep until next midnight
                    tomorrow = datetime.now() + timedelta(days=1)
                    next_midnight = datetime.combine(tomorrow.date(), datetime.min.time())
                    sleep_seconds = max((next_midnight - datetime.now()).total_seconds(), 0)
                    self.logger.info(msg=f'Pipeline ran successfully! The program will sleep until {next_midnight}.')
                    t.sleep(sleep_seconds)
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(msg='Exception happened while running the main pipeline!')
                self.logger.error(traceback.format_exc())
                break


    def start_consumers(self):
        topics = ['processed-data', 'processed-data-15m', 'predicted-data', 'predicted-data-15m']
        for topic in topics:
            consumer = SimpleConsumer()
            thread = threading.Thread(target=consumer.main, args=(topic, topic))
            thread.daemon = True
            self.consumers.append(thread)
            thread.start()


    def pipeline(self):
        # calculate starting and ending dates
        if self.starting_date_1m is None and self.starting_date_15m is None:
            self.starting_date_1m = str((datetime.now() - timedelta(days=14)).isoformat()).split('T')[0] + 'T00:00:00Z'
            self.starting_date_15m = str((datetime.now() - timedelta(days=90)).isoformat()).split('T')[0] + 'T00:00:00Z'
        
        self.ending_date_15m = str((datetime.now() - timedelta(days=1)).isoformat()).split('T')[0] + 'T00:00:00Z'
        self.ending_date_1m = str((datetime.now() - timedelta(days=1)).isoformat()).split('T')[0] + 'T00:00:00Z'

        # create dataset
        raw_df_1m = self.dataset_creator.main(start=self.starting_date_1m, stop=self.ending_date_1m, line='L301', timeframe='1m', machine='Blower-Pump-1')
        raw_df_15m = self.dataset_creator.main(start=self.starting_date_15m, stop=self.ending_date_15m, line='L301', timeframe='15m', machine='Blower-Pump-1')

        # produce raw data
        self.producer.main(topic='raw-data', df=raw_df_1m)
        self.producer.main(topic='raw-data-15m', df=raw_df_15m)

        # fetch raw data from druid
        t.sleep(60)  # wait for druid to consume the raw data from kafka topics
        df_1m = self.druid_fetcher.main(topic='raw-data')
        df_15m = self.druid_fetcher.main(topic='raw-data-15m')

        # pre-process data
        processed_df_1m = self.preprocesser.main(df=df_1m)
        processed_df_15m = self.preprocesser.main(df=df_15m)

        # produce processed data
        self.producer.main(topic='processed-data', df=processed_df_1m)
        self.producer.main(topic='processed-data-15m', df=processed_df_15m)

        # fetch processed data from druid
        t.sleep(60)  # wait for druid to consume the processed data from kafka topics
        df_1m = self.druid_fetcher.main(topic='processed-data')
        df_15m = self.druid_fetcher.main(topic='processed-data-15m')

        # run lstm model
        results_1m, predicted_data_1m = self.lstm_model.main(load_best_model=True, df=df_1m, input_days=14, output_days=2, interval_minute=1)
        results_15m, predicted_data_15m = self.lstm_model.main(load_best_model=False, df=df_15m, input_days=90, output_days=10, interval_minute=15)

        # produce predicted data and insert model results into postgre db
        if results_1m is not None and predicted_data_1m is not None:
            self.producer.main(topic='predicted-data', df=predicted_data_1m)
            self.postgre_client.insert_data(table_name='model_results_1m', results=results_1m)

        if results_15m is not None and predicted_data_15m is not None:
            self.producer.main(topic='predicted-data-15m', df=predicted_data_15m)
            self.postgre_client.insert_data(table_name='model_results_15m', results=results_15m)

        # update starting dates as dataframes' last rows
        self.starting_date_1m = raw_df_1m['time'].iloc[-1]
        self.starting_date_15m = raw_df_15m['time'].iloc[-1]


if __name__ == '__main__':
    run_pipeline = RunPipeline()
    run_pipeline.run()