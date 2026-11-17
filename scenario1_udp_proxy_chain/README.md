# 情境一：多程序 UDP 代理串聯轉發 — 量化測試報告

> **狀態：已修復並驗證**。第 2、3 節為修復前的原始實測與問題分析（行號對應修復前版本）；第 4、5 節為修復內容與修復後驗證結果。

## 1. 測試環境與拓撲架構

- **執行環境**：Python 3.10.6（僅使用標準函式庫）
- **節點與埠號配置**：
  - `client.py`：UDP Client（動態綁定本機埠號，目標 `127.0.0.1:8888`）
  - `proxy1.py`：綁定 `127.0.0.1:8888`，Client 與 Proxy2 之間的雙向轉發
  - `proxy2.py`：綁定 `127.0.0.1:8889`，將字串轉為大寫 (`.upper()`) 後轉發至 Server，並將 Server 回應轉回 Proxy1
  - `server.py`：綁定 `127.0.0.1:12345`，接收後將封包回傳給發送方位址（即 Proxy2）

修復前的封包流向：

```text
[Client] ──(100 筆, 每 0.1s)──> [Proxy1 :8888] ──> [Proxy2 :8889] <══(無限乒乓迴圈)══> [Server :12345]
   ▲
   └── (阻塞等待 Proxy1 回傳，永不結束)
```

修復後的封包流向：

```text
去程：[Client] ──> [Proxy1 :8888] ──> [Proxy2 :8889] ──(轉大寫)──> [Server :12345]
回程：[Client] <── [Proxy1 :8888] <── [Proxy2 :8889] <──────────── [Server :12345]
```

---

## 2. 修復前量化實測數據（測試視窗：11.5 秒）

| 量化指標 | 設定值 / 預期值 | 實測數值 | 狀態與說明 |
| :--- | :---: | :---: | :--- |
| **Client 發送封包總數** | 100 筆 | **100 筆** | 每筆間隔 `0.1s`，共耗時約 `9.9s` 發送完畢 |
| **Client 單筆封包大小** | 67 ~ 69 Bytes | **67 ~ 69 Bytes** | 內容：`"UDP Server sends Packet i to UDP Client as the i-th transmission."` |
| **Proxy1 (`:8888`) 接收並轉發數** | 100 筆 | **100 筆 (100%)** | 完整接收 Client 的 100 筆封包並轉發至 Proxy2 |
| **Proxy2 (`:8889`) 大寫轉換率** | 100% | **100%** | 成功轉為 `"UDP SERVER SENDS PACKET ..."` |
| **Server (`:12345`) 11.5 秒內接收總數** | 100 筆 | **400,592 筆** (~34,834 封包/秒) | **異常暴增**：因 `Server` 與 `Proxy2` 發生無限回音風暴 (Echo Storm) |
| **Client 接收到回傳封包數** | 1 筆 | **0 筆** | `client.py` 卡在第 16 行 `client_socket.recvfrom(1024)` 永久阻塞 |

---

## 3. 修復前之關鍵問題分析

### 問題一：`Proxy2` 與 `Server` 之間的 UDP 無限迴圈風暴（11.5 秒產生 40 萬筆封包）
1. 在 `server.py` 第 15–17 行：
   ```python
   data, client_address = server_socket.recvfrom(1024)
   server_socket.sendto(data, client_address)
   ```
   因為封包是由 `Proxy2` (`127.0.0.1:8889`) 發送給 `Server`，所以 `Server` 看到的 `client_address` 是 `('127.0.0.1', 8889)`（即 `Proxy2`），並將封包回傳給 `Proxy2`。
2. 在 `proxy2.py` 第 11–13 行：
   ```python
   proxy1_data, proxy1_address = proxy2_socket.recvfrom(1024)
   modified_data = proxy1_data.decode('utf-8').upper().encode('utf-8')
   proxy2_socket.sendto(modified_data, server_address)
   ```
   `Proxy2` 並未檢查來源位址 `proxy1_address` 是否為 `Proxy1`，因此當它收到 `Server` 回傳的封包時，誤以為是新的封包，再次轉成大寫送回給 `Server` (`127.0.0.1:12345`)，形成本機迴路風暴（實測每秒來回約 **3.48 萬次**）。

### 問題二：`Client` 永久阻塞於 `recvfrom(1024)`
- `client.py` 第 16 行執行 `data, _ = client_socket.recvfrom(1024)` 等待回應，且未設定 `settimeout()`。
- 由於 `Proxy2` 與 `Proxy1` 皆只實作了單向轉發（`Client -> Proxy1 -> Proxy2 -> Server`），沒有將 `Server` 的回應沿原路（`Server -> Proxy2 -> Proxy1 -> Client`）傳回給 `Client`，導致 `client.py` 發完 100 筆封包後永久卡住無法結束。

---

## 4. 修復內容

| 檔案 | 修改 | 對應問題 |
| :--- | :--- | :---: |
| `proxy2.py` | 依來源位址分流：來自 `Proxy1 (:8888)` 的封包轉大寫後送 `Server`；來自 `Server (:12345)` 的回應轉回 `Proxy1`，**不再送回 Server**；其他來源一律丟棄 | 問題一、二 |
| `proxy1.py` | 依來源位址分流：來自 `Proxy2 (:8889)` 的回應轉回最後記錄的 `Client` 位址；其他來源視為 Client 請求，記錄其位址後轉發至 `Proxy2`。移除未使用的 `multiprocessing` | 問題二 |
| `client.py` | 發送完成後以 `settimeout(2.0)` 逐筆接收回應，收滿 100 筆或逾時即結束，並印出收發統計；Proxy1 未啟動時印出提示後結束 | 問題二 |
| `server.py` | 加上接收計數 (`Received #n`)，方便觀察是否仍有迴圈 | — |
| 全部節點 | `recvfrom()` 捕捉 `ConnectionResetError`（Windows 上目的端關閉時回傳的 ICMP Port Unreachable），避免程序崩潰 | 穩定性 |

---

## 5. 修復後驗證結果

### 5.1 主要測試（Server、Proxy2、Proxy1 啟動後執行 Client 一次）

| 量化指標 | 修復前 | 修復後 | 結果 |
| :--- | :---: | :---: | :---: |
| Server 接收總數（Client 結束當下） | 400,592 筆（11.5 秒內） | **100 筆** | ✅ |
| Server 接收總數（Client 結束後再等 5 秒） | 持續暴增 | **100 筆**（無增加） | ✅ 迴圈已消除 |
| Proxy1 轉發至 Proxy2 / 回傳至 Client | 100 / 0 筆 | **100 / 100 筆** | ✅ |
| Client 接收回應數 | 0 筆（永久阻塞） | **100 / 100 筆**（0 遺失） | ✅ |
| Client 執行結果 | 不會結束 | **約 11 秒內正常結束**（exit code 0） | ✅ 不再阻塞 |
| 回應內容 | — | 全部為大寫 `UDP SERVER SENDS PACKET i ...` | ✅ |
| 回應順序 | — | 封包編號 1 → 100 依序到達 | ✅ |
| 各節點錯誤 / Traceback | — | 無 | ✅ |

Client 最後輸出：

```text
Sent 100 packets, received 100 responses (0 lost).
```

### 5.2 邊界測試

| 測試情境 | 預期行為 | 實測結果 |
| :--- | :--- | :--- |
| 未啟動任何 Proxy / Server，單獨執行 Client | 不阻塞，正常結束 | ✅ 印出 `Proxy1 is unreachable.` 與 `received 0 responses (100 lost)` 後結束 |
| 同一組 Server / Proxy 連續執行 Client 兩次 | 兩次皆完整收發，Proxy 不因前一個 Client 關閉而崩潰 | ✅ 兩次皆 `100 / 100`，Server 累計 200 筆，無 Traceback |

測試結束後 `8888`、`8889`、`12345` 埠皆已釋放，無殘留程序。

---

## 6. 執行方式

依序在不同終端機啟動（先啟動接收端，再啟動 Client）：

```bash
python server.py
python proxy2.py
python proxy1.py
python client.py
```

`server.py`、`proxy1.py`、`proxy2.py` 為常駐程序，測試完畢後以 `Ctrl+C` 結束。

---

## 7. 已知限制

- **Proxy1 只記錄最後一個 Client 位址**：若多個 Client 同時發送，所有回應都會轉給最後發送的那一個 Client。本情境只有單一 Client，不受影響；若要支援多 Client，需在封包中攜帶 Client 識別資訊，或為每個 Client 建立獨立的上游 socket。
- **Client 在發送完畢後才開始讀取回應**：發送期間回應暫存在作業系統的 UDP 接收緩衝區中。100 筆小封包不會溢出緩衝區；若大幅增加封包數或封包大小，可能需要改為以獨立執行緒同時收發。
