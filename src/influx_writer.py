from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv
from _logger import ProjectLogger
import traceback
import os
import time
from datetime import datetime

class InfluxWriter:
    load_dotenv()
    TOKEN = os.getenv('MY_INFLUX_TOKEN')
    logger = ProjectLogger(class_name='InfluxWriter').create_logger()

    def __init__(self, token:str, url:str, organization:str):
        self.token = token
        self.url = url
        self.organization = organization
        self.bucket = None

        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.organization)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.logger.info(msg='Influx DB writer api client successfully created!')


    def write_into_influxdb(self, bucket:str, data:dict):
        try:
            data['time'] = datetime.fromisoformat(data['time'])
            self.bucket = bucket
            if self.bucket == 'predicted-data' or self.bucket == 'predicted-data-15m':
                point = (
                    Point(measurement_name='prediction')
                    .time(data['time'])
                    .tag('topic', bucket)
                    .field('PredictedAxialAxisRmsVibration', float(data['PredictedAxialAxisRmsVibration']))
                )
            else:
                point = (
                    Point(measurement_name='sensor_data')
                    .time(data['time'])
                    .tag('topic', bucket)
                    .field('machine', data['machine'])
                    .field('axialAxisRmsVibration', float(data['axialAxisRmsVibration']))
                    .field('radialAxisKurtosis', float(data['radialAxisKurtosis']))
                    .field('radialAxisPeakAcceleration', float(data['radialAxisPeakAcceleration']))
                    .field('radialAxisRmsAcceleration', float(data['radialAxisRmsAcceleration']))
                    .field('radialAxisRmsVibration', float(data['radialAxisRmsVibration']))
                    .field('temperture', float(data['temperature']))
                )
            self.write_api.write(bucket=self.bucket, org=self.organization, record=point)
            #self.logger.info(msg=f'Data uploaded successfully into {self.bucket} named Influx DB bucket.')
        except Exception as e:
            self.logger.error(msg=f'Exception happened while writing into {self.bucket} named Influx DB bucket!')
            self.logger.error(msg=traceback.format_exc())


    def close_connection(self):
        self.client.close()