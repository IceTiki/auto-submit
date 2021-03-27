import yaml
import requests
from todayLoginService import TodayLoginService
from autoSign import AutoSign
from collection import Collection


def getYmlConfig(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(config)


class Qmsg:
    def __init__(self, config):
        # config={'key':'*****','qq':'*****','isgroup':0}
        self.config = config

    def send(self, msg):
        # msg：要发送的信息|消息推送函数
        msg = str(msg)
        sendtype = 'group/' if self.config['isgroup'] else 'send/'
        res = requests.post(url='https://qmsg.zendee.cn/'+sendtype +
                            self.config['key'], data={'msg': msg, 'qq': self.config['qq']})
    #    code = res.json()['code']
    #    print(code)


def main():
    config = getYmlConfig()
    exeinfo = {}
    exeinfo.clear
    for i in range(7):
        for user in config['users']:
            try:
                print('\n=========================\n' +
                      user['user']['username']+'\n=========================\n')

                username = user['user']['username']
                if username in exeinfo:
                    if not exeinfo[username] == 1:
                        continue
                exeinfo[username] = 1

                today = TodayLoginService(user['user'])
                today.login()
                # 登陆成功，通过type判断当前属于 信息收集、签到、查寝
                # 信息收集
                if user['user']['type'] == 0:
                    # 以下代码是信息收集的代码
                    collection = Collection(today, user['user'])
                    collection.queryForm()
                    collection.fillForm()
                    msg = collection.submitForm()
                    print(msg)
                elif user['user']['type'] == 1:
                    # 以下代码是签到的代码
                    sign = AutoSign(today, user['user'])
                    unsigntaskExeInfo = sign.getUnSignTask()
                    if type(unsigntaskExeInfo) != dict:
                        exeinfo[username] = unsigntaskExeInfo
                        continue
                    else:
                        unsigntaskExeInfo = unsigntaskExeInfo['taskName']
                    sign.getDetailTask()
                    sign.fillForm()
                    msg = sign.submitForm()
                    exeinfo[username] = unsigntaskExeInfo+msg
                    Qmsg({'key': user['user']['key'], 'qq': user['user']['qq'], 'isgroup': 0}).send(
                        username+unsigntaskExeInfo+msg)
                    print('\n=========================\n'+unsigntaskExeInfo +
                          '\n=========================\n'+msg+'\n=========================\n')
            except Exception as e:
                print(str(e))
    print('\n==\n==\n'*10)
    print(yaml.dump(exeinfo, allow_unicode=True))


# 阿里云的入口函数
def handler(event, context):
    main()


# 腾讯云的入口函数
def main_handler(event, context):
    main()
    return 'ok'


if __name__ == '__main__':
    main()
