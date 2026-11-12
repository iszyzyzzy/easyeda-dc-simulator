# PCB DC Lab / 铜皮压降分析原型

本地运行的 Python + 浏览器工具，不上传电路到第三方，无 CDN。**这是早期工程原型，不是签核级 PI/热仿真软件。**

## 启动（Linux）

```bash
cd pcb_dc
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:8765`。默认演示板可直接运行。应用仅监听 localhost；不要未经安全加固暴露公网。

- 选择网络、电压源引脚和一个或多个恒流负载。
- 铜厚输入空白时保留导入叠层；填写则覆盖所有层。
- 先用较粗网格运行，再点击“网格减半，检查收敛”。最大压降变化低于 5% 只是提示，不代表验证通过。
- 可切换电位、压降、局部电阻损耗密度，鼠标查看数值，导出结果 JSON。
- 整体热阻选填。温升 = 总铜损 × 用户提供的热阻。**损耗图不是温度图**。

## 嘉立创专业版 V3 项目

官方文档描述的 **文件夹格式** `.eprj3`（JSON 中 `format: "folder"`）是项目索引，实际 PCB 位于 `pcb/*.epcb2`，仅上传这种索引不能得到铜皮。不能仅根据扩展名判断一个文件是否完整：程序会优先检查文件内容，ZIP 容器即使名为 `.eprj3` 也会尝试读取。未知单文件格式会明确提示未识别，不会断言其不完整。

参考：[官方 EPRJ3 skill 格式说明](https://github.com/easyeda/easyeda-eprj3-skill/blob/main/docs/format-reference.md)。单文件导出可能与目录格式不同，目前只支持 ZIP 内含一个 `.epcb2` 的归档，不宣称覆盖所有单文件容器。

支持上传单个 `.epcb2` 或包含一个 PCB 的完整项目 ZIP，也可从本地项目路径启动：

```bash
python app.py --project /path/to/project/project.eprj3
# 或 --project /path/to/project-directory
```

导入器使用最终 POURED 几何而不是铺铜边界。请先在 EDA 重新铺铜并保存。缺失铺铜、未解析封装/导电几何等会写入 `validation_errors` 并阻止求解。导入假设显示在 UI；请和 EDA 对照几何、网络、坐标、焊盘和孔洞。

**当前重要限制：** 新版 EPRJ3 的所有变体未覆盖。VIA 层跨度未可靠解析时会阻止该网络求解，而不是擅自当作通孔。特殊焊盘、部分封装铜图元也会阻止求解。需要用户实际项目继续做兼容适配。

## 数值模型

均匀正方形网格，铜内相邻单元中心用电阻连接：`G = thickness / rho`，`rho(20°C)=1.724e-8 Ωm`，铜温度系数 0.00393/K。边界绝缘。源焊盘覆盖单元为 Dirichlet 电压边界；负载电流均分到焊盘覆盖单元。稀疏线性系统计算电位，边功率 `G ΔV²` 分到两端单元。每次检查 KCL、电源电流和总功率平衡。

中间 JSON 可显式描述多层及过孔：过孔桶壁电阻 `rho L / [π((d/2+t)²-(d/2)²)]`。多层连接按给定层顺序均分桶壁长度。桶壁每层只接一个已解析铜单元，因此过孔附近的电流拥挤与局部损耗具有明显网格依赖性；不适合用来判断过孔热点。没有精确叠层高度时此近似不适合内层分流精度验证。端子不会在钻孔中心创建虚假铜；未解析到铜时拒绝或有限距离吸附到已有铜单元。

未包含：回流网络、接触电阻、连接器电阻、源内阻、恒功率负载、电热耦合迭代、FR4/空气/散热器热传导、瞬态。负载焊盘不是严格等电位超节点。过孔局部损耗按连接单元分摊，热点绝对峰值具有网格依赖性。窄颈、间隙、热焊盘至少跨数个网格，否则必须细化。

## 中间 JSON

见 `examples/demo.json`。单位统一 mm：

- `layers`: `{id,name,thickness_um}`。
- `copper`: `{net,layer,polygon:[[x,y],...],holes:[[[x,y],...]]}`，同网络同层多边形取并集。
- `pins`: `{id,label,net,layer,x,y,radius_mm}`。
- `vias`: `{net,x,y,diameter_mm,drill_mm,layers:[id,...],length_mm,plating_um}`。
- `warnings` 和 `validation_errors`：前者显示，后者阻止求解。`validation_errors_by_net` 按明确的网络单独阻断。

## 检查

```bash
python -m unittest discover -s tests -v
```

包含矩形铜条解析电阻比对、I²R 缩放、电流守恒、断网、孔洞断路、端子重叠、过孔、网格上限和温升公式测试。UI JavaScript 做语法检查；本执行环境 Chromium 无法创建 socket，未能完成浏览器视觉验证。程序可在普通 Linux 浏览器运行，但首次交付需用户实际板验证 EPRJ3 导入与几何显示。

## 本次验证记录

- 求解器矩形铜条与解析 `ρL/(wt)` 符合，电流/功率守恒通过。
- 演示板 24 V、5 A 单负载：h=0.5 / 0.25 / 0.125 mm 时最大压降分别 9.7220 / 9.7220 / 9.6995 mV，铜损 48.0455 / 48.0406 / 47.9244 mW。这只是该演示模型的收敛，不是普遍误差保证。
- 官方 easyeda-pro-eprj3-format 示例 PCB1 导入 26 个引脚、131 铜多边形、1 个 PTH。跨层 PTH 源到 C2.1 的 GND 连通求解通过；孤立 C1.1 与 VCC 引脚断路被拒绝。示例源文件未随包分发。
- 本地 HTTP 服务、示例加载、求解 API、跨域写入拒绝均有自动测试。
