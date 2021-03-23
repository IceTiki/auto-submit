# 获取正确的任务
def getrighttask(self, tasks, title):
    # tasks=res.json()['datas']['unSignedTasks']
    # 当userinfo中的title填上0时，自动匹配最后一个签到任务
    if len(tasks) < 1:
        print('当前没有未签到任务')
        return '当前没有未签到任务'
    if title == 0:
        latestTask = tasks[0]
        return {'signInstanceWid': latestTask['signInstanceWid'], 'signWid': latestTask['signWid']}
    for righttask in tasks:
        if righttask['taskName'] == title:
            print(righttask['taskName'])
            return {'signInstanceWid': righttask['signInstanceWid'], 'signWid': righttask['signWid']}

self.taskInfo = self.getrighttask(res['datas']['unSignedTasks'],self.userInfo['title'])

# 返回一些签到的信息
def getSignInfo(self):
    return {'user': self.userInfo['username'],'title':self.taskName,'msg':self.msg}

