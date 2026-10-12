-- Mesen Lua Script: 監視擴展頭像系統的記憶體存取
-- 用法: 在 Mesen 中 Debug → Script Window，載入此腳本後按 F5 執行

-- PRG ROM 位址 (已扣除 iNES header)
local PORTRAIT_TABLES = {
    -- 標準頭像系統
    {name = "標準指標表", start = 0x1BC28, length = 324},  -- 81 * 4 bytes
    {name = "標準排列表", start = 0x1B0C4, length = 2916}, -- 81 * 36 bytes

    -- 擴展頭像系統
    {name = "擴展選擇器", start = 0x1EFD4, length = 174},  -- 174 portraits
    {name = "擴展排列表", start = 0x1ED04, length = 720},  -- 20 * 36 bytes

    -- 變體 tiles (相對於 Group A base 0x1D694)
    {name = "變體眼睛區", start = 0x1DE04, length = 960},  -- tiles 120-179
    {name = "變體臉部區", start = 0x1E984, length = 960},  -- tiles 180-239
    {name = "變體嘴巴區", start = 0x1EB44, length = 1920}, -- tiles 240-359
}

-- 記錄讀取事件
local readLog = {}
local logEnabled = true
local maxLogEntries = 100

function formatHex(value, digits)
    return string.format("%0" .. digits .. "X", value)
end

function getTableName(prgAddr)
    for _, tbl in ipairs(PORTRAIT_TABLES) do
        if prgAddr >= tbl.start and prgAddr < tbl.start + tbl.length then
            local offset = prgAddr - tbl.start
            return tbl.name, offset
        end
    end
    return nil, 0
end

function onPrgRead(addr, value)
    if not logEnabled then return end

    local tableName, offset = getTableName(addr)
    if tableName then
        local state = emu.getState()
        local pc = state.cpu.pc
        local a = state.cpu.a
        local x = state.cpu.x
        local y = state.cpu.y

        local entry = string.format(
            "PC=$%04X  Read %s[%d] = $%02X  (PRG $%05X)  A=$%02X X=$%02X Y=$%02X",
            pc, tableName, offset, value, addr, a, x, y
        )

        table.insert(readLog, entry)
        emu.log(entry)

        -- 限制日誌大小
        if #readLog > maxLogEntries then
            table.remove(readLog, 1)
        end
    end
end

-- 註冊 callback
for _, tbl in ipairs(PORTRAIT_TABLES) do
    emu.addMemoryCallback(onPrgRead, emu.callbackType.read, tbl.start, tbl.start + tbl.length - 1, emu.memType.prgRom)
end

-- 控制函數
function pauseLog()
    logEnabled = false
    emu.log("=== 日誌暫停 ===")
end

function resumeLog()
    logEnabled = true
    emu.log("=== 日誌恢復 ===")
end

function clearLog()
    readLog = {}
    emu.log("=== 日誌清除 ===")
end

function showLog()
    emu.log("=== 最近 " .. #readLog .. " 筆記錄 ===")
    for i, entry in ipairs(readLog) do
        emu.log(entry)
    end
end

emu.log("=== 頭像系統監視腳本已啟動 ===")
emu.log("監視區域:")
for _, tbl in ipairs(PORTRAIT_TABLES) do
    emu.log(string.format("  %s: PRG $%05X - $%05X", tbl.name, tbl.start, tbl.start + tbl.length - 1))
end
emu.log("")
emu.log("進入遊戲並查看武將頭像，相關記憶體存取會顯示在這裡")
emu.log("提示: 可在 Script 視窗的 Console 中呼叫 pauseLog(), resumeLog(), showLog()")
