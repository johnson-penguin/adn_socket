# 情境二：多路徑 UDP 掉包、延遲與批次重傳模擬 — 量化測試報告

## 1. 測試環境與架構配置

- **執行環境**：Python 虛擬環境 (`.env`)
- **節點與綁定埠號 (Local Loopback UDP)**：
  - `Server`：`127.0.0.1:5405`
  - `Proxy1`：`127.0.0.1:5406`（模擬封包遺失路徑）
  - `Client`：`127.0.0.1:5407`
  - `Proxy2`：`127.0.0.1:5408`（模擬封包延遲路徑，單次延遲 `0.5s`）

---

## 2. `Q3.py` 量化測試結果

### 參數設定
- **傳送間隔**：`0.1s` / 封包
- **Client 接收逾時 (Timeout)**：`5.0s`
- **各路徑模擬條件**：
  - **Path 1 (`Server -> Proxy1 -> Client`)**：設定 `20%` 隨機掉包率 (`random.random() < 0.2`)
  - **Path 2 (`Server -> Proxy2 -> Client`)**：設定 `50%` 隨機延遲率 (`random.random() < 0.5`，觸發時 `time.sleep(0.5)`)
  - **Path 3 (`Client -> Server`)**：直線傳送（程式碼第 147、154 行 `client_send_thread` 被註解）

### 實測數據表（以 100 筆封包實時傳輸與原始 Path 3 測試）

| 測試路徑 | 傳送封包數 | 實測接收數 (`receive_buffer`) | 實測遺失數 (`loss_buffer`) | 實測延遲數 (`delay_buffer`) | 實測掉包率 (理論值) | 實測延遲率 (理論值) | 總執行耗時 (含 5s Timeout) | 程序結束狀態 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Path 1 (Proxy1)** | 100 | 80 | 20 | 0 | **20.0%** (20%) | **0.0%** (0%) | **15.70 s** | 主程序印出結果後卡住（背景執行緒未設 `daemon=True`） |
| **Path 2 (Proxy2)** | 100 | 100 | 0 | 51 | **0.0%** (0%) | **51.0%** (50%) | **31.54 s** | 主程序印出結果後卡住（背景執行緒未設 `daemon=True`） |
| **Path 3 (Direct)** | 0 *(註解未啟動)* | 0 | 0 | 0 | `ZeroDivisionError` | — | **5.00 s** | 於第 165 行除以零崩潰 (`loss_buffer / (0 + 0)`) |

> **1,000 筆封包耗時推算與佇列效應分析**：
> - **Path 1 (1,000 筆)**：`1000 × 0.1s + 5s (timeout) ≈ 105.0 s`。
> - **Path 2 (1,000 筆)**：由於 `proxy2_receive_and_send` 為單執行緒阻塞式 `time.sleep(0.5)`，當 Server 每 `0.1s` 發送一筆且 `50%` 封包延遲 `0.5s` 時，平均每筆封包在 Proxy2 消耗 `0.25s` 處理時間（大於發送間隔 `0.1s`），封包會在作業系統 UDP Socket Buffer 中排隊，1,000 筆總耗時約為 `500 × 0.5s + 5s ≈ 255.0 s`。

---

## 3. `Q4.py` 量化測試結果（全 6 種組合）

### 參數設定
- **總封包數 (`num_packet`)**：`50` 筆
- **批次大小 (`packet_group_size`)**：`10` 筆 / 批（共 `5` 批）
- **傳送間隔**：`0.1s`（單筆模式發送 50 次；批次模式發送 5 次）
- **Client 接收逾時 (Timeout)**：`2.0s`
- **各路徑模擬條件**：
  - **Path 1 (`Proxy1`)**：設定 `30%` 隨機掉包率 (`random.random() < 0.3`)
  - **Path 2 (`Proxy2`)**：設定 `5%` 隨機延遲率 (`random.random() < 0.05`，延遲 `0.5s`)
  - **Path 3 (`Proxy1 + Proxy2` 分流)**：前 `30%` (`proportion = 0.3`，即前 2 批 `1~20` 號封包) 走 `Proxy1`，後 `70%` (後 3 批 `21~50` 號封包) 走 `Proxy2`

### 實測數據表

| 路徑選擇 | 傳輸模式 | 發送次數 (封包/批次) | 實測接收數 (`receive_buffer`) | 實測遺失數 (`loss_buffer`) | 實測延遲數 (`delay_buffer`) | 實測掉包率 (設定值) | 實測延遲率 (設定值) | Path 1 / Path 2 選擇次數 | 總耗時 (含 2s Timeout) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Path 1 (Proxy1)** | `1` 單筆 (Single) | 50 封包 | 36 | 14 | 0 | **28.0%** (30%) | **0.0%** (0%) | 0 / 0 | **7.35 s** |
| **Path 1 (Proxy1)** | `2` 批次 (Multi) | 5 批次 | 3 | 2 | 0 | **40.0%** (30%) | **0.0%** (0%) | 0 / 0 | **2.35 s** |
| **Path 2 (Proxy2)** | `1` 單筆 (Single) | 50 封包 | 50 | 0 | 3 | **0.0%** (0%) | **6.0%** (5%) | 0 / 0 | **7.38 s** |
| **Path 2 (Proxy2)** | `2` 批次 (Multi) | 5 批次 | 5 | 0 | 0 | **0.0%** (0%) | **0.0%** (5%) | 0 / 0 | **2.44 s** |
| **Path 3 (混合分流)** | `1` 單筆 (Single) | 0 *(未實作分支)* | 0 | 0 | 0 | `ZeroDivisionError` | — | 0 / 0 | **5.05 s** |
| **Path 3 (混合分流)** | `2` 批次 (Multi) | 5 批次 | 4 | 1 | 1 | **20.0%** | **25.0%** | **2 次 / 3 次** | **2.95 s** |

---

## 4. `text.py` 測試結果

| 測試腳本 | 測試內容 | 實測輸出 | 執行狀態 |
| :--- | :--- | :---: | :--- |
| `text.py` | 解析批次字串 `"Hi, I am server 991 ... 993\n"` 尾端封包編號 | `993` | 正常結束 (`exit code 0`) |

---

## 5. 實測發現之程式碼問題彙整

1. **背景執行緒未設為 Daemon 導致程序無法自動結束 (`Q3.py`、`Q4.py`)**：
   - `proxy1_thread` 與 `proxy2_thread` 內部為 `while True:` 無窮迴圈，且建立 `threading.Thread` 時未設定 `daemon=True`。當 `client_receive_thread.join()` 超時結束並印出統計結果後，Python 程序仍會卡在背景執行緒的 `recvfrom()`。
2. **重傳接收執行緒被註解 (`Q4.py` 第 242、247 行)**：
   - `#server_receive_thread = threading.Thread(target=server_receive_data)` 被註解，因此當 Client 偵測到掉包並發送 `REQUEST_RETRANSMISSION` 至 Server (`5405`) 時，Server 端沒有執行緒接收並處理重傳請求。
3. **單筆模式下封包檢查步進值固定為 `+10` (`Q4.py` 第 182 行)**：
   - `client_receive_data()` 固定執行 `client_last_sent_packet += 10`（針對 `packet_group_size = 10` 的批次模式設計）。若選擇單筆模式 (`transmissions_choice == "1"`)，收到的第 1 筆封包編號為 `1`，但預期值變為 `10`，導致每一筆單筆封包都被誤判為缺包並觸發重傳等待。
4. **`Q4.py` 單筆模式缺少 Path 3 分支 (`Q4.py` 第 56–68 行)**：
   - `server_send_single_data()` 僅處理 `choice == "1"` 與 `choice == "2"`，未處理 `choice == "3"`，導致選擇 `Path 3 + Single` 時不會發出任何 UDP 封包，並在最後計算掉包率時觸發 `ZeroDivisionError`。
5. **`Q3.py` Path 3 未啟動 `client_send_thread` (`Q3.py` 第 147、154 行)**：
   - 選擇 Path 3 時因發送執行緒被註解，5 秒後 `receive_buffer` 與 `loss_buffer` 皆為 `0`，於第 165 行觸發 `ZeroDivisionError`。
