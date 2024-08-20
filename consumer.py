from confluent_kafka import Consumer, KafkaException
from mongodb import MongoDB


class SimpleConsumer:
    db_username = 'catchthebalina'
    db_password = 'whaleBot_1104'
    db_cluster = 'Whales'
    db_client = MongoDB(username=db_username, password=db_password, cluster_name=db_cluster)

    def __init__(self, topic:str, properties_file:str) -> None:
        self.topic = topic
        self.properties_file = properties_file
        self.consumer_config = {}

        # create consumer config
        self.read_config()

        # create consumer object using config dict
        self.consumer = Consumer(self.consumer_config)


    def main(self):
        try:
            self.consume_messages()
        except Exception as e:
            print(e)


    def read_config(self):
        with open(self.properties_file) as fh:
            for line in fh:
                line = line.strip()
                if len(line) != 0 and line[0] != '#':
                    parameter, value = line.strip().split('=', 1)
                    self.consumer_config[parameter] = value
        self.consumer_config['group.id'] = 'python-group-1'
        self.consumer_config['auto.offset.reset'] = 'earliest'


    def consume_messages(self):
        self.consumer.subscribe(topics=[self.topic])
        while True:
            try:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error() is not None:
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        continue
                    else:
                        print(f'Error: {msg.error()}')
                        break
                msg = f'key: {msg.key()} - value: {msg.value()}'
                print(msg)
                msg = {
                    'date': msg.split(', ')[0],
                    'open': msg.split(', ')[1], 
                    'high': msg.split(', ')[2],
                    'low': msg.split(', ')[3]
                    #'close': msg.split(', ')[4]
                }
                self.db_client.write_data(data=msg)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f'Exception happened when consuming messages, error: {e}')


if __name__ == '__main__':
    simple_consumer = SimpleConsumer(
        topic='test-topic-2',
        properties_file='client.properties'
    )

    simple_consumer.main()