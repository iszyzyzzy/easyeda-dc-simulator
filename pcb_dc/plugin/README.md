# 嘉立创专业版 PCB DC Lab 只读导出插件（实验版）

本插件只读取**当前打开的 PCB**，选择一个网络后导出 API 快照 JSON。
在本地 PCB DC Lab 上传 JSON 后，由 `api_importer.py` 转为求解器格式，
再选择源引脚/负载、电压/电流。没有联网、远程执行桥接或 PCB 修改操作。

## 安装与使用

1. 运行 `python plugin/build.py`（在 `pcb_dc` 目录内），生成
   `plugin/pcb-dc-readonly-export.eext`。仓库中也附有该实验包。
2. 在嘉立创专业版扩展管理中使用本地扩展导入功能导入 `.eext`。
   具体入口随客户端版本变化；插件还没有在真实 EDA 客户端联调验证。
3. 打开目标 PCB，**手动重新铺铜**，导出期间不要编辑或切换文档。
4. 菜单「PCB DC Lab → 只读导出当前网络…」，选择网络，确认实际铜厚、板厚和孔铜厚。
5. 保存 `pcb-dc-api.json`，在本地独立程序上传这个文件。插件本身不运行数值求解。

纯走线（Line/Arc）、纯铺铜以及混合网络都会读取；不会要求一定存在铺铜。
覆铜使用 `getCopperRegion().getState_PourFills()` 最终结果，不使用 Pour 外边框。
焊盘先从各元件 `getAllPins()` 读取，再合并独立焊盘；同名焊盘按元件 ID 去重。
物理钻孔在按网络筛选前单独采集，包含无网络安装孔及其他网络过孔；
求解器在全部铜合并后扣除这些孔，避免走线把孔中心重新填实。旧插件快照缺孔清单时会要求重导出。
所有 API 几何单位按 mil 转为 mm，**不使用文件 POURED 格式的 ×10 系数**。

## 明确限制

- **当前只支持双层板**。多层板阻断，不能把 API 图层枚举顺序当作物理叠层。
- 普通通孔 `ViaType=0` 支持；盲埋/缝合过孔阻断。PTH 的圆形镀孔支持。
- 铜厚、板厚和孔铜厚由用户明确输入。v4.2+ 的物理叠层 API 原始返回值保存在快照中，
  但其字段未在客户端验证，不擅自解析或覆盖用户值。默认示例值不是对实际板的测量。
- 自定义多边形焊盘、圆角矩形、非圆 ELLIPSE、特殊分层焊盘、槽孔/偏心孔目前阻断。
- 未支持的带网络图元（如独立 Fill/Polyline）明确阻断，而不是静默漏铜。
- beta API 不存在、最终铺铜不可取得或未识别的几何会形成阻断错误。
- 快照读取不是原子操作；导出期间不要改板。请在求解前与 EDA 对比几何。
- 数值模型、网格误差与发热限制同独立版。损耗图不是温度场。

## 构建与测试

无需 npm 包；`build.py` 对两个固定模块生成官方 SDK 所用的 IIFE 全局导出形式
`edaEsbuildExportName`，并按官方 `.eext` ZIP 布局打包。它不是通用 JS 编译器。

```sh
python plugin/build.py
node --check plugin/dist/index.js
node --test plugin/test_exporter.mjs
python -m unittest discover -s tests -v
```

测试为模拟 API 的读取/去重/错误路径、几何转换与求解器集成，不等于真实客户端安装测试。

依据官方文档：
- https://github.com/easyeda/easyeda-api-skill
- https://github.com/easyeda/easyeda-api-sdk

本实现独立编写，未复制 SDK 源码。打包格式参考 SDK 的公开配置。
