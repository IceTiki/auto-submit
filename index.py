import yaml
import requests
from todayLoginService import TodayLoginService
from autoSign import AutoSign
from collection import Collection
import time


def getYmlConfig(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(config)


def log(*args):
    if args:
        string = '|||log|||'+'\n'
        for item in args:
            string += str(item)
        print(string)


class Qmsg:
    def __init__(self, config):
        # config={'key':'*****','qq':'*****','isgroup':0}
        self.config = config

    def send(self, msg):
        # msg：要发送的信息|消息推送函数
        msg = str(msg)
        # 简单检查配置
        if self.config['key'] == '' or self.config['qq'] == '' or msg == '' or '*' in self.config['key'] or '*' in self.config['qq']:
            print('Qmsg配置出错')
            return
        sendtype = 'group/' if self.config['isgroup'] else 'send/'
        res = requests.post(url='https://qmsg.zendee.cn/'+sendtype +
                            self.config['key'], data={'msg': msg, 'qq': self.config['qq']})
    #    code = res.json()['code']
    #    print(code)


def notification(exeinfo, config, startExecutingTime):
    ExecutingTime=startExecutingTime-time.time()
    yaml_Exeinfo = yaml.dump(exeinfo, allow_unicode=True)
    log(yaml_Exeinfo)
    log('执行时间%.3fSecond'%ExecutingTime)
    for user in config['users']:
        if 'remarksName' in user['user']:
            if user['user']['remarksName']:
                yaml_Exeinfo = yaml_Exeinfo.replace(
                    user['user']['username'], user['user']['remarksName'])
    Qmsg(config['notification']).send(yaml_Exeinfo+'\n执行时间%.3fSecond'%ExecutingTime)


def main():
    startExecutingTime =time.time()
    config = getYmlConfig()
    exeinfo = {}
    exeinfo.clear
    for executingTimes in range(config['maxRetryTimes']):
        logStr_ExecutingTimes = '|第%d次尝试|' % (executingTimes+1)
        for user in config['users']:
            try:
                log(user['user']['username'])
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
                    log(msg)
                elif user['user']['type'] == 1:
                    # 以下代码是签到的代码
                    sign = AutoSign(today, user['user'])
                    unsigntaskExeInfo = sign.getUnSignTask()
                    if type(unsigntaskExeInfo) != dict:
                        exeinfo[username] = unsigntaskExeInfo + \
                            logStr_ExecutingTimes
                        continue
                    else:
                        unsigntaskExeInfo = unsigntaskExeInfo['taskName']
                    sign.getDetailTask()
                    sign.fillForm()
                    msg = sign.submitForm()
                    exeinfo[username] = unsigntaskExeInfo + \
                        msg+logStr_ExecutingTimes
                    Qmsg({'key': user['user']['key'], 'qq': user['user']['qq'], 'isgroup': 0}).send(
                        username+unsigntaskExeInfo+msg+logStr_ExecutingTimes)
                    log(unsigntaskExeInfo, msg)
            except Exception as e:
                print(str(e))
    notification(exeinfo, config, startExecutingTime)


# 阿里云的入口函数
def handler(event, context):
    main()


# 腾讯云的入口函数
def main_handler(event, context):
    main()
    return 'ok'


if __name__ == '__main__':
    main()
