# -*- coding: utf-8 -*-
import sys
import requests
import json
import yaml
import oss2
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from urllib3.exceptions import InsecureRequestWarning
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

# debug模式
debug = False
if debug:
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


a# 读取yml配置
def getYmlConfig(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(config)


# 全局配置
config = getYmlConfig(yaml_file='config.yml')


# 获取今日校园api
def getCpdailyApis(user):
    apis = {}
    user = user['user']
    schools = requests.get(
        url='https://www.cpdaily.com/v6/config/guest/tenant/list', verify=not debug).json()['data']
    flag = True
    for one in schools:
        if one['name'] == user['school']:
            if one['joinType'] == 'NONE':
                log(user['school'] + ' 未加入今日校园')
                exit(-1)
            flag = False
            params = {
                'ids': one['id']
            }
            res = requests.get(url='https://www.cpdaily.com/v6/config/guest/tenant/info', params=params,
                               verify=not debug)
            data = res.json()['data'][0]
            joinType = data['joinType']
            idsUrl = data['idsUrl']
            ampUrl = data['ampUrl']
            if 'campusphere' in ampUrl or 'cpdaily' in ampUrl:
                parse = urlparse(ampUrl)
                host = parse.netloc
                res = requests.get(parse.scheme + '://' + host)
                parse = urlparse(res.url)
                apis[
                    'login-url'] = idsUrl + '/login?service=' + parse.scheme + r"%3A%2F%2F" + host + r'%2Fportal%2Flogin'
                apis['host'] = host

            ampUrl2 = data['ampUrl2']
            if 'campusphere' in ampUrl2 or 'cpdaily' in ampUrl2:
                parse = urlparse(ampUrl2)
                host = parse.netloc
                res = requests.get(parse.scheme + '://' + host)
                parse = urlparse(res.url)
                apis[
                    'login-url'] = idsUrl + '/login?service=' + parse.scheme + r"%3A%2F%2F" + host + r'%2Fportal%2Flogin'
                apis['host'] = host
            break
    if flag:
        log(user['school'] + ' 未找到该院校信息，请检查是否是学校全称错误')
        exit(-1)
    log(apis)
    return apis


# 获取当前utc时间，并格式化为北京时间
def getTimeStr():
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime("%Y-%m-%d %H:%M:%S")


# 输出调试信息，并及时刷新缓冲区
def log(content):
    print(getTimeStr() + ' ' + str(content))
    sys.stdout.flush()


# 登陆并返回session
def getSession(user, loginUrl):
    user = user['user']
    params = {
        'login_url': loginUrl,
        # 保证学工号和密码正确下面两项就不需要配置
        'needcaptcha_url': '',
        'captcha_url': '',
        'username': user['username'],
        'password': user['password']
    }

    cookies = {}
    # 借助上一个项目开放出来的登陆API，模拟登陆
    res = requests.post(config['login']['api'], params, verify=not debug)
    cookieStr = str(res.json()['cookies'])
    log(cookieStr)
    if cookieStr == 'None':
        log(res.json())
        return None

    # 解析cookie
    for line in cookieStr.split(';'):
        name, value = line.strip().split('=', 1)
        cookies[name] = value
    session = requests.session()
    session.cookies = requests.utils.cookiejar_from_dict(cookies)
    return session


# 查询表单
def GetForm(session, apis):
    host = apis['host']
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.4; OPPO R11 Plus Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 Safari/537.36 yiban/8.1.11 cpdaily/8.1.11 wisedu/8.1.11',
        'content-type': 'application/json',
        'Accept-Encoding': 'gzip,deflate',
        'Accept-Language': 'zh-CN,en-US;q=0.8',
        'Content-Type': 'application/json;charset=UTF-8'
    }
    SignInfosInOneDayWidUrl = 'https://{host}/wec-counselor-sign-apps/stu/sign/getStuSignInfosInOneDay'.format(host=host)#获取今日签到列表
    params = {}
    res = session.post(SignInfosInOneDayWidUrl, headers=headers, data=json.dumps(params), verify=not debug)#将params打包为json格式
    if len(res.json()['datas']['unSignedTasks']) < 1:#还没有签到的项目['datas']['unSignedTasks']
        return None
    signInstanceWid = res.json()['datas']['unSignedTasks'][0]['signInstanceWid']#重要数据signInstanceWid
    signWid = res.json()['datas']['unSignedTasks'][0]['signWid']#重要数据signWid
    detailCollector = 'https://{host}/wec-counselor-sign-apps/stu/sign/detailSignInstance'.format(host=host)#打开签到页面
    res = session.post(url=detailCollector, headers=headers,
                       data=json.dumps({"signInstanceWid":signInstanceWid,"signWid":signWid})#利用之前获取的signInstanceWid和signWid发包
                       , verify=not debug)
    longitude = res.json()['datas']['signPlaceSelected'][0]['longitude']#签到范围中心经度
    latitude = res.json()['datas']['signPlaceSelected'][0]['latitude']#签到范围中心纬度
    extraFieldItems = res.json()['datas']['extraField'][0]['extraFieldItems']#表单
    form = {'signInstanceWid': signInstanceWid, 'signWid': signWid, 'longitude': longitude, 'latitude': latitude, 'extraFieldItems': extraFieldItems}
    print(form)#看看有没有拉对表单
    return form


# 获取默认选项和其对应的ID
def extraFieldItem(session, form, host):
    sort = 1
    extraFieldItems = form['extraFieldItems']
    for EFItems in extraFieldItems[:]:
        answer = config['cpdaily']['answer']#注意：这是一个要在配置文件设置的项：默认选项
        if EFItems['content'] == answer:
            extraFieldItemValue = EFItems['content']#默认选项
            extraFieldItemWid= EFItems['wid']#默认选项对应的ID
            return {'extraFieldItemValue' : extraFieldItemValue, 'extraFieldItemWid' : extraFieldItemWid}
    print('没有匹配到问题的wid')
    exit(-1)


# 提交表单
def submitForm(signInstanceWid, longitude, latitude, position, extraFieldItemValue, extraFieldItemWid, session, host):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.4; OPPO R11 Plus Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 Safari/537.36 okhttp/3.12.4',
        'CpdailyStandAlone': '0',
        'extension': '1',
        'Cpdaily-Extension': '1wAXD2TvR72sQ8u+0Dw8Dr1Qo1jhbem8Nr+LOE6xdiqxKKuj5sXbDTrOWcaf v1X35UtZdUfxokyuIKD4mPPw5LwwsQXbVZ0Q+sXnuKEpPOtk2KDzQoQ89KVs gslxPICKmyfvEpl58eloAZSZpaLc3ifgciGw+PIdB6vOsm2H6KSbwD8FpjY3 3Tprn2s5jeHOp/3GcSdmiFLYwYXjBt7pwgd/ERR3HiBfCgGGTclquQz+tgjJ PdnDjA==',
        'Content-Type': 'application/json; charset=utf-8',
        # 请注意这个应该和配置文件中的host保持一致
        'Host': host,
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip'
    }

    # 默认正常的提交参数json
    params = {"signInstanceWid":signInstanceWid,"longitude":longitude,"latitude":latitude,"isMalposition":0,"abnormalReason":"","signPhotoUrl":"","position":position,"isNeedExtra":1,"extraFieldItems":[{"extraFieldItemValue":extraFieldItemValue,"extraFieldItemWid":extraFieldItemWid}]}
    # print(params)
    submitForm = 'https://{host}/wec-counselor-sign-apps/stu/sign/submitSign'.format(host=host)#提交表单url
    r = session.post(url=submitForm, headers=headers,
                     data=json.dumps(params), verify=not debug)
    print(params)
    msg = r.json()['message']
    return msg

title_text = '今日校园疫结果通知'

# 发送邮件通知
def sendMessage(send, msg):
    if send != '':
        log('正在发送邮件通知。。。')
        res = requests.post(url='http://www.zimo.wiki:8080/mail-sender/sendMail',
                            data={'title': title_text, 'content': getTimeStr() + str(msg), 'to': send})

        code = res.json()['code']
        if code == 0:
            log('发送邮件通知成功。。。')
        else:
            log('发送邮件通知失败。。。')
            log(res.json())

def sendEmail(send,msg):
    my_sender= config['Info']['Email']['account']   # 发件人邮箱账号
    my_pass = config['Info']['Email']['password']         # 发件人邮箱密码
    my_user = send      # 收件人邮箱账号，我这边发送给自己
    try:
        msg=MIMEText(getTimeStr() + str(msg),'plain','utf-8')
        msg['From']=formataddr(["FromRunoob",my_sender])  # 括号里的对应发件人邮箱昵称、发件人邮箱账号
        msg['To']=formataddr(["FK",my_user])              # 括号里的对应收件人邮箱昵称、收件人邮箱账号
        msg['Subject']=title_text               # 邮件的主题，也可以说是标题

        server=smtplib.SMTP_SSL(config['Info']['Email']['server'], config['Info']['Email']['port'])  # 发件人邮箱中的SMTP服务器，端口是25
        server.login(my_sender, my_pass)  # 括号中对应的是发件人邮箱账号、邮箱密码
        server.sendmail(my_sender,[my_user,],msg.as_string())  # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
        server.quit()  # 关闭连接
    except Exception:  # 如果 try 中的语句没有执行，则会执行下面的 ret=False
        log("邮件发送失败")
    else: print("邮件发送成功")

# server酱通知
def sendServerChan(msg):
    log('正在发送Server酱。。。')
    res = requests.post(url='https://sc.ftqq.com/{0}.send'.format(config['Info']['ServerChan']),
                            data={'text': title_text, 'desp': getTimeStr() + "\n" + str(msg)})
    code = res.json()['errmsg']
    if code == 'success':
        log('发送Server酱通知成功。。。')
    else:
        log('发送Server酱通知失败。。。')
        log('Server酱返回结果'+code)

# Qmsg酱通知
def sendQmsgChan(msg):
    log('正在发送Qmsg酱。。。')
    res = requests.post(url='https://qmsg.zendee.cn:443/send/{0}'.format(config['Info']['Qsmg']),
                            data={'msg': title_text + '\n时间：' + getTimeStr() + "\n 返回结果：" + str(msg)})
    code = res.json()['success']
    if code:
        log('发送Qmsg酱通知成功。。。')
    else:
        log('发送Qmsg酱通知失败。。。')
        log('Qmsg酱返回结果'+code)

# 综合提交
def InfoSubmit(msg, send=None):
    if(None != send):
        if(config['Info']['Email']['enable']): sendEmail(send,msg)
        else: sendMessage(send, msg)
    if(config['Info']['ServerChan']): sendServerChan(msg)
    if(config['Info']['Qsmg']): sendQmsgChan(msg)


def main_handler(event, context):
    try:
        for user in config['users']:
            log('当前用户：' + str(user['user']['username']))
            apis = getCpdailyApis(user)
            log('脚本开始执行。。。')
            log('开始模拟登陆。。。')
            session = getSession(user, apis['login-url'])
            if session != None:
                log('模拟登陆成功。。。')
                log('正在查询最新待填写问卷。。。')
                getFormparams = GetForm(session, apis)
                if str(getFormparams) == 'None':
                    log('获取最新待填写问卷失败，可能是辅导员还没有发布。。。')
                    InfoSubmit('没有新问卷')
                    exit(-1)
                log('查询最新待填写问卷成功。。。')
                log('正在自动填写问卷。。。')
                EFform = extraFieldItem(session, getFormparams, apis['host'])
                log('填写问卷成功。。。')
                log('正在自动提交。。。')
                msg = submitForm(getFormparams['signInstanceWid'], getFormparams['longitude'], getFormparams['latitude'], user['user']['address'], EFform['extraFieldItemValue'], EFform['extraFieldItemWid'], session, apis['host'])
                if msg == 'SUCCESS':
                    log('自动提交成功！')
                    InfoSubmit('自动提交成功！', user['user']['email'])
                elif msg == '该收集已填写无需再次填写':
                    log('今日已提交！')
                    # InfoSubmit('今日已提交！', user['user']['email'])
                    InfoSubmit('今日已提交！')
                else:
                    log('自动提交失败。。。')
                    log('错误是' + msg)
                    InfoSubmit('自动提交失败！错误是' + msg, user['user']['email'])
                    exit(-1)
            else:
                log('模拟登陆失败。。。')
                log('原因可能是学号或密码错误，请检查配置后，重启脚本。。。')
                exit(-1)
    except Exception as e:
        InfoSubmit("出现问题了！"+str(e))
        raise e
    else:
        return 'success'


# 配合Windows计划任务等使用
if __name__ == '__main__':
    print(main_handler({}, {}))
    # for user in config['users']:
    #     log(getCpdailyApis(user))
