-- Mesen Lua Script: 追蹤大眾臉頭像組件索引表讀取
-- 用法: 在 Mesen 中 Debug → Script Window，載入此腳本後按 F5 執行
--
-- 已確認發現:
--   組件索引表: CPU $B024 (ROM $1F034)
--   索引方式: portrait_index - 81 (不是 char_index - 39)
--   每角色 5 bytes: [Cat, Head, Eye, Nose, Mouth]
--   record_addr = $B024 + (portrait_index - 81) * 5
--
-- 全自動模式: 腳本啟動後立即監視，偵測到讀取後自動分析

-- ============================================================
-- 組件索引表參數
-- ============================================================
local COMP_TABLE_BASE = 0xB024   -- CPU 位址 (ROM $1F034)
local COMP_NAMES = {"Cat", "Head", "Eye", "Nose", "Mouth"}
local PORTRAIT_OFFSET = 81       -- table_index = portrait_index - 81

-- 監視範圍: 組件表 174 筆 × 5 bytes = 870 bytes
-- $B024 到 $B38A (再多留一點空間)
local TRACE_START = 0xB020
local TRACE_END   = 0xB3A0

-- 追蹤狀態
local readLog = {}
local batchCount = 0
local frameCounter = 0
local lastReadFrame = -999
local BATCH_GAP = 30

-- 將 CPU 位址轉換為 ROM 偏移 (Bank 7)
local function cpuToRom(cpuAddr)
    return cpuAddr - 0x8000 + 0x1C010
end

-- ============================================================
-- 分析並輸出一個批次的讀取記錄
-- ============================================================
local function analyzeBatch(batch, batchNum)
    -- 過濾: 只保留值 0-19 的讀取 (組件索引合理範圍)
    local filtered = {}
    for _, e in ipairs(batch) do
        if e.value >= 0 and e.value <= 19 then
            table.insert(filtered, e)
        end
    end

    if #filtered == 0 then return end

    emu.log("")
    emu.log(string.format("========== 批次 #%d: %d 筆有效讀取 ==========", batchNum, #filtered))

    -- 嘗試按 5 個一組分析
    local groupIdx = 0
    local i = 1
    while i <= #filtered do
        -- 取當前位址，計算 portrait_index
        local baseAddr = filtered[i].cpuAddr
        local offset = baseAddr - COMP_TABLE_BASE
        local ti = offset / 5
        local posInRecord = offset % 5

        -- 如果不是 record 開頭 (posInRecord != 0)，單獨輸出
        if posInRecord ~= 0 or ti ~= math.floor(ti) then
            emu.log(string.format("  CPU $%04X (ROM $%05X) = %d  (非對齊讀取, offset=%d)",
                baseAddr, cpuToRom(baseAddr), filtered[i].value, offset))
            i = i + 1
        else
            -- 嘗試收集完整的 5-byte record
            local portraitIdx = math.floor(ti) + PORTRAIT_OFFSET
            local vals = {}
            local count = 0
            for j = 0, 4 do
                if i + j <= #filtered and filtered[i + j].cpuAddr == baseAddr + j then
                    vals[j] = filtered[i + j].value
                    count = count + 1
                else
                    break
                end
            end

            if count == 5 then
                emu.log(string.format(
                    "  P%03d (ti=%d): Cat=%d  Head=%d  Eye=%d  Nose=%d  Mouth=%d   [$%04X-$%04X]",
                    portraitIdx, math.floor(ti),
                    vals[0], vals[1], vals[2], vals[3], vals[4],
                    baseAddr, baseAddr + 4
                ))
                i = i + 5
            else
                -- 不完整，逐一輸出
                emu.log(string.format("  P%03d? (ti=%d): 不完整 (%d bytes) @ $%04X",
                    portraitIdx, math.floor(ti), count, baseAddr))
                for j = 0, count - 1 do
                    emu.log(string.format("    %s = %d", COMP_NAMES[j + 1] or "?", vals[j]))
                end
                i = i + count
            end
        end
    end

    emu.log(string.format("========== 批次 #%d 結束 ==========", batchNum))
    emu.log("")
end

-- ============================================================
-- 讀取 callback
-- ============================================================
local function onTraceRead(addr, value)
    local currentFrame = frameCounter

    -- 如果距離上次讀取超過 BATCH_GAP frames，且有累積資料 → 輸出上一批
    if #readLog > 0 and (currentFrame - lastReadFrame) > BATCH_GAP then
        batchCount = batchCount + 1
        analyzeBatch(readLog, batchCount)
        readLog = {}
    end

    table.insert(readLog, {
        cpuAddr = addr,
        romAddr = cpuToRom(addr),
        value = value,
        frame = currentFrame
    })

    lastReadFrame = currentFrame
end

-- 註冊 callback
emu.addMemoryCallback(
    onTraceRead,
    emu.callbackType.read,
    TRACE_START,
    TRACE_END,
    emu.memType.cpuMemory
)

-- 每 frame 檢查是否有待輸出的批次
emu.addEventCallback(function()
    frameCounter = frameCounter + 1
    if #readLog == 0 then return end
    if (frameCounter - lastReadFrame) > BATCH_GAP then
        batchCount = batchCount + 1
        analyzeBatch(readLog, batchCount)
        readLog = {}
    end
end, emu.eventType.endFrame)

-- ============================================================
-- 啟動訊息
-- ============================================================
emu.log("=== 大眾臉組件索引表追蹤腳本 v3 ===")
emu.log("")
emu.log("已確認結構:")
emu.log("  表位置: CPU $B024 (ROM $1F034)")
emu.log("  索引:   portrait_index - 81")
emu.log("  格式:   5 bytes = [Cat, Head, Eye, Nose, Mouth]")
emu.log("  公式:   addr = $B024 + (portrait_index - 81) * 5")
emu.log("")
emu.log("已驗證:")
emu.log("  P081 周泰 (ti=0): $B024 → [3,0,2,3,1]")
emu.log("  P085 曹豹 (ti=4): $B038 → [2,0,1,3,1] = Cat=2,Head=0,Eye=1,Nose=3,Mouth=1")
emu.log("")
emu.log("待驗證:")
emu.log("  P083 孫瑜 (ti=2): $B02E → 預期 [?,1,2,1,2]  (Head=1,Eye=2,Nose=1,Mouth=2)")
emu.log("")
emu.log("正在監視中，觸發頭像即可看到解析結果...")
