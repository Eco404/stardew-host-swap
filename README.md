# stardew-host-swap

一个用于 **《星露谷物语》1.6版本多人联机存档主客身份互换** 的 Python 工具。

当前项目的目的是：  
在拿到联机农场主机存档后，将某个已有的联机客机角色提升为新的主机角色，同时尽量保留角色数据、存档预览信息，以及一部分关键的玩家归属关系。

## 开源协议

本项目采用 **MIT License** 开源。

---

## 简介

《星露谷物语》的联机存档中：

- 主机玩家位于存档文件的 `SaveGame/player` 节点下
- 联机客机位于存档文件的 `SaveGame/farmhands/Farmer` 节点下

从存档结构上看，主机和客机虽然都属于 `Farmer` 类型，但并不是简单的“改个名字就能互换”。  
直接交换节点后，往往还会遇到：

- `SaveGameInfo` 预览信息不一致
- `mailReceived` 导致的进度缺失
- `homeLocation` 未修正导致联机角色列表不显示
- `userID` 绑定问题
- `farmhandReference`、`owner`、`ownerID` 等归属引用未同步

这个项目就是为了解决这些问题而写的。

---

## 当前功能

当前版本支持以下内容：

- 交换主存档中 `player` 与指定 `farmhands/Farmer` 的角色数据
- 同步修复 `SaveGameInfo`
- 修复 `mailReceived`
- 修复 `homeLocation`
- 修复 `userID`
- 修复部分基于 `UniqueMultiplayerID` 的归属字段：
  - `farmhandReference`
  - `owner`
  - `ownerID`
- 支持 **预检查 / 报告模式**
- 支持直接传入 **存档文件夹路径**
- 支持 **原地修改原存档文件**
- 自动创建 `_bak` 备份文件

---

## 使用方法

### 1. 准备环境

需要：

- Python 3.10 或更高版本
- 一个《星露谷物语》联机存档文件夹，Windows下一般位于 `%appdata%\StardewValley\Saves` 路径下

典型存档目录结构如下：

```text
name_123456789/
  name_123456789
  SaveGameInfo
```

其中：

- 文件夹名：`name_123456789`
- 主存档文件：`name_123456789`
- 预览信息文件：`SaveGameInfo`

### 2. 列出存档中的主机和所有客机角色

```bash
python main.py "\path\to\name_123456789" --list
```

### 3. 预检查（推荐先执行）

按角色名选择（`NAME`是需要与当前主机交换数据的客机玩家名称）：

```bash
python main.py "\path\to\name_123456789" --target-name NAME --report
```

或按 `UniqueMultiplayerID` 选择（`ID`是需要与当前主机交换数据的客机玩家ID）：

```bash
python main.py "\path\to\name_123456789" --target-id ID --report
```

执行后将输出数据交换的修改结果，但不会进行实际文件操作

### 4. 实际执行交换

```bash
python main.py "\path\to\name_123456789" --target-name NAME
```

执行该命令后会：

- 备份原主存档为：`原文件名_bak`
- 备份`SaveGameInfo`为：`SaveGameInfo_bak`
- 将`NAME`客机玩家的数据与主机玩家的数据进行交换
- 将修改后的内容写回原存档文件

---

## 运行逻辑

当前版本的处理流程大致如下：

1. 读取主存档 XML，找到：
   - `SaveGame/player`
   - 目标 `SaveGame/farmhands/Farmer`

2. 使用 **原始 XML 文本级别** 的方式，交换：
   - `player` 节点内部内容
   - 指定 `Farmer` 节点内部内容

3. 在交换完成后，对以下字段做定点修复：
   - `mailReceived`
   - `homeLocation`
   - `userID`

4. 同步修复部分归属引用：
   - `farmhandReference`
   - `owner`
   - `ownerID`

5. 将交换后的 `player` 内容同步写入 `SaveGameInfo/Farmer`

6. 在写回前自动备份原文件为 `_bak`

---

## 技术实现

<details>
<summary>点击展开</summary>

### 1. 玩家主要数据交换方式

主体交换并不是整棵树重建，而是：

- 找到 `<player>...</player>` 的内部区间
- 找到目标 `<Farmer>...</Farmer>` 的内部区间
- 直接交换这两段内部 XML 内容

### 2. SaveGameInfo 的同步方式

`SaveGameInfo` 的根节点是 `Farmer`，并且通常带有：

- `xmlns:xsi`
- `xmlns:xsd`

当前实现不会替换根标签，也不会改这两个命名空间声明，  
只会把交换后主存档中的 `player` 内部内容，覆盖到 `SaveGameInfo/Farmer` 的内部内容。

### 3. mailReceived 的处理策略

当前采用的是“保主机进度优先”的策略：

- 新主机：`原客机 mailReceived ∪ 原主机 mailReceived`
- 新客机：恢复为原客机自己的 `mailReceived`

这样做是因为主机的 `mailReceived` 中存有全局进度标志，尽量避免主机切换后丢失全局进度标志。

### 4. homeLocation 的处理策略

测试表明，如果主机交换为客机后仍保留：

```xml
<homeLocation>FarmHouse</homeLocation>
```

那么它在联机角色选择列表中可能不会显示。

因此当前修复规则为：

- 新主机：`homeLocation = FarmHouse`
- 新客机：`homeLocation = 目标客机交换前原本的小屋 location`

### 5. userID 的处理策略

当前按“位置语义”处理：

- 新主机：`userID = 空`
- 新客机：恢复为目标客机交换前的 `userID`

### 6. farmhandReference / owner / ownerID 的处理方式

当前版本会对以下标签做双向 ID 替换：

- `farmhandReference`
- `owner`
- `ownerID`

逐个命中标签值，按原值判断：

- 原值是旧主机 ID → 写成旧客机 ID
- 原值是旧客机 ID → 写成旧主机 ID

### 7. 写入策略

- 先备份主存档为 `原文件名_bak`
- 如果存在 `SaveGameInfo`，先备份为 `SaveGameInfo_bak`
- 再将修改后的内容写回原文件名

这样在测试失败时，可以直接用备份文件回滚。

</details>

---

## 注意事项

### 1. 工具会自动备份，但仍建议手动备份整个存档文件夹

当前版本会自动创建 `_bak` 文件，但在涉及重要存档时，仍然建议手动额外备份整个存档文件夹。

### 2. 该工具属于实验性工具

仅在1.6.15版本进行了多轮测试，该项目更适合作为：

- 个人使用工具
- 针对原版或较少模组环境的实验性工具

如果你的存档使用了大量模组，可能还会存在：

- 自定义字段未同步
- 模组附加 owner 字段未修复
- 额外 world/player 绑定未覆盖

### 3. 并非所有问题都已完全解决

当前工具重点解决的是：

- 角色主体互换
- 角色可见性
- 基础进度同步
- 一部分归属关系

但还没有覆盖所有可能的多人/模组边角情况。

---

## 已知限制

- 尚未系统处理所有可能的 `UniqueMultiplayerID` 引用字段
- 尚未专门适配模组自定义节点
- 尚未迁移主屋 / Cabin 的室内家具与布局
- 尚未对所有版本差异做兼容层

---

## 建议的使用流程

建议按下面顺序使用：

1. 先执行 `--list`
2. 再执行 `--report`
3. 确认目标角色、ID、预期修改内容无误
4. 再执行实际交换
5. 进入游戏测试：
   - 是否能正常载入
   - 主机角色是否正确
   - 原主机是否出现在联机角色列表
   - 房屋和归属是否符合预期
6. 如出现问题，可用 `_bak` 文件手动回滚

---

## 免责声明

本项目为非官方工具。  
使用前请务必自行备份存档。  
因存档损坏、角色异常、联机问题或模组兼容问题造成的损失，使用者需自行承担风险.

---

## 开发方式说明

本项目开发过程中使用了 AI 辅助工具。  
AI 参与了部分代码生成、重构、问题排查与文档编写工作。

为保证可用性，所有实际功能均经过人工测试与验证后发布。
