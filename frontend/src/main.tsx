import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, theme, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import App from './App'
import './index.css'

dayjs.locale('zh-cn')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#2f7cf6',
          colorInfo: '#2f7cf6',
          colorSuccess: '#36b37e',
          colorWarning: '#f5a623',
          colorError: '#f4574d',
          borderRadius: 10,
          fontSize: 14,
        },
        components: {
          Layout: { bodyBg: 'transparent', siderBg: 'transparent', headerBg: 'transparent' },
          Card: { colorBgContainer: 'rgba(22,27,34,0.62)' },
        },
      }}
    >
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
