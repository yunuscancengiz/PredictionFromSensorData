from confluent_kafka import Producer, Consumer, KafkaException
from fetch_finance_data import FetchData
import time

class ApprovedProducer:
    def __init__(self, topic:str, symbol:str, properties_file:str, approving_topic:str, approving_properties_file:str) -> None:
        self.topic = topic
        self.symbol = symbol
        self.properties_file = properties_file
        self.approving_topic = approving_topic
        self.approving_properties_file = approving_properties_file
        self.producer_config = {}
        self.consumer_config = {}
        self.messages = []
        self.is_approved = True

        # prepare config file
        self.read_config()

        # create producer object using config dict
        self.producer = Producer(self.producer_config)
        self.consumer = Consumer(self.consumer_config)


    def main(self):
        while True:
            try:
                if self.is_approved:
                    print(self.is_approved)
                    self.messages = FetchData(symbol=self.symbol).fetch()
                    self.produce_messages()
                    print('produce messages çalıştı')
                    self.messages = []  # @TODO: karşıdan onay gelince sıfırlayacak hale getir
                    print('mesaj listesi boşaltıldı')
                    self.is_approved = False
                    print(self.is_approved)
                else:
                    self.consume_messages()
                    print('consume messages çalıştı')
            except Exception as e:
                print(e)
            except KeyboardInterrupt:
                break


    def read_config(self):
        with open(self.properties_file) as fh:
            for line in fh:
                line = line.strip()
                if len(line) != 0 and line[0] != '#':
                    parameter, value = line.strip().split('=', 1)
                    self.producer_config[parameter] = value.strip()

        with open(self.approving_properties_file) as fh:
            for line in fh:
                line = line.strip()
                if len(line) != 0 and line[0] != '#':
                    parameter, value = line.strip().split('=', 1)
                    self.consumer_config[parameter] = value.strip()
        self.consumer_config["group.id"] = "python-group-1"
        self.consumer_config["auto.offset.reset"] = "earliest"


    @staticmethod
    def delivery_report(err, msg):
        if err is not None:
            print(f'Delivery failed for {msg.key()}, error: {err}')
            return
        print(f'Record:{msg.key()} successfully produced to topic:{msg.topic()} partition:[{msg.partition()}] at offset:{msg.offset()}')


    def parse_messages(self, index:int):
        key = str(self.messages.loc[index, 'Date'])
        value = f"{str(self.messages.loc[index, 'Open'])}, {str(self.messages.loc[index, 'High'])}, {str(self.messages.loc[index, 'Low'])}, {str(self.messages.loc[index, 'Close'])}"
        return key, value
    

    def consume_messages(self):
        self.consumer.subscribe(topics=[self.approving_topic])
        while True:
            try:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        continue
                    else:
                        print(f'Error: {msg.error()}')
                        break
                msg = f'key: {msg.key()} value: {msg.value()}'
                self.is_approved = True
                return msg
            except Exception as e:
                print(f'Exception happened when consuming messages, error: {e}')
            except KeyboardInterrupt:
                break


    def produce_messages(self):
        for index in range(len(self.messages)):
            try:
                if self.is_approved == True:
                    message_key, message_value = self.parse_messages(index=index)
                    self.producer.produce(key=message_key, value=message_value, topic=self.topic, on_delivery=self.delivery_report)    
            except BufferError:
                self.producer.poll(0.1)
            except Exception as e:
                print(f'Exception while producing message - index: {index}, Err: {e}')
            except KeyboardInterrupt:
                break
        self.producer.flush()
        time.sleep(10)
        self.is_approved = False


if __name__ == '__main__':
    appr_producer = ApprovedProducer(
        topic='test-topic-2',
        symbol='AAPL',
        properties_file='client.properties',
        approving_topic='test-topic-3',
        approving_properties_file='client2.properties'
    )

    appr_producer.main()