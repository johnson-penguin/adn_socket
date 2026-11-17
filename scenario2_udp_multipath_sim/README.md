# 情境二：多路徑 UDP 掉包、延遲與批次重傳模擬

> **狀態：已修復並驗證**。各子題的問題分析、修復內容與實測數據請見子資料夾 README。

## 子題

| 資料夾 | 程式 | 主題 |
| :--- | :--- | :--- |
| **[q3_loss_delay_measure/](./q3_loss_delay_measure/README.md)** | `Q3.py` | 單筆傳輸下，量測各路徑的掉包率與延遲率 |
| **[q4_batch_multipath_retransmit/](./q4_batch_multipath_retransmit/README.md)** | `Q4.py`、`text.py` | 單筆 / 批次傳輸、雙路徑分流，以及掉包偵測與重傳 |

## 共用架構

兩個子題皆為**單一程式**，以 4 個執行緒在同一個 Python 程序內模擬所有節點，使用本機回送位址 (Loopback) 的 UDP：

| 節點 | 位址 | 角色 |
| :--- | :--- | :--- |
| `Server` | `127.0.0.1:5405` | 傳送端（Q3 Path 3 時為接收端；Q4 另負責處理重傳要求） |
| `Proxy1` | `127.0.0.1:5406` | 模擬**封包遺失**路徑 |
| `Client` | `127.0.0.1:5407` | 接收端（Q3 Path 3 時為傳送端） |
| `Proxy2` | `127.0.0.1:5408` | 模擬**封包延遲**路徑（每次延遲 `0.5s`） |

```text
            ┌──> [Proxy1 :5406]（隨機丟棄）──┐
[Server :5405]                               ├──> [Client :5407]
            └──> [Proxy2 :5408]（隨機延遲）──┘
```

> 兩支程式綁定相同埠號，**不可同時執行**。

## 執行方式

```bash
cd q3_loss_delay_measure
python Q3.py              # 互動式選擇路徑
python Q3.py 1 100        # 參數：路徑 (1/2/3)、封包數

cd q4_batch_multipath_retransmit
python Q4.py              # 互動式選擇路徑與傳輸模式
python Q4.py 3 2          # 參數：路徑 (1/2/3)、傳輸模式 (1 = 單筆, 2 = 批次)
```
