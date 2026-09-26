"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import road as router_road
from app.routers import bridge as router_bridge
from app.routers import tunnel as router_tunnel
from app.routers import patrol as router_patrol
from app.routers import disease as router_disease
from app.routers import assess as router_assess
from app.routers import plan as router_plan
from app.routers import work as router_work
from app.routers import accept as router_accept
from app.routers import pothole as router_pothole
from app.routers import crack as router_crack
from app.routers import snow as router_snow
from app.routers import drain as router_drain
from app.routers import light as router_light
from app.routers import material as router_material
from app.routers import equip as router_equip
from app.routers import fund as router_fund
from app.routers import complaint as router_complaint
from app.routers import archive as router_archive

ROUTERS = [router_road, router_bridge, router_tunnel, router_patrol, router_disease, router_assess, router_plan, router_work, router_accept, router_pothole, router_crack, router_snow, router_drain, router_light, router_material, router_equip, router_fund, router_complaint, router_archive]
