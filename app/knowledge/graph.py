"""金融知识图谱：NetworkX 多重有向图存储实体关系，支持智能推荐、异常检测、关联分析。

节点 = ("user"|"account"|"merchant"|"product"|"transaction", 实体键)，属性挂在节点上；
边 = 带关系标签 rel ∈ {owns, transacts_with, holds, transfers_to, made, at}。
对外 API 与旧手写实现保持一致，调用方零改动；统计类数据由图结构即时派生。
"""

from collections import Counter
from typing import Dict, List

import networkx as nx


def _n(kind: str, key) -> tuple:
    """类型化节点键，避免不同实体类型的 ID 撞名。"""
    return (kind, key)


class FinancialKnowledgeGraph:
    """金融知识图谱（NetworkX MultiDiGraph）"""

    def __init__(self):
        self.g = nx.MultiDiGraph()

    # ------------------------------------------------ 实体与关系写入

    def add_user(self, user_id: str, user_info: dict):
        """添加用户实体"""
        self.g.add_node(_n("user", user_id), **{"type": "user", **user_info})

    def add_account(self, account_id, account_info: dict, owner_id: str):
        """添加账户实体和拥有关系"""
        self.g.add_node(_n("account", account_id), **{"type": "account", **account_info})
        self.g.add_edge(_n("user", owner_id), _n("account", account_id), rel="owns")

    def add_merchant(self, merchant_name: str, merchant_info: dict):
        """添加商户实体"""
        self.g.add_node(_n("merchant", merchant_name), **{"type": "merchant", **merchant_info})

    def add_product(self, product_code: str, product_info: dict):
        """添加产品实体"""
        self.g.add_node(_n("product", product_code), **{"type": "product", **product_info})

    def add_transaction(self, txn_id: str, txn_info: dict, user_id: str, merchant_name=None):
        """添加交易实体和关系（用户—交易、用户—商户、交易—商户）"""
        self.g.add_node(_n("transaction", txn_id), **{"type": "transaction", **txn_info})
        self.g.add_edge(_n("user", user_id), _n("transaction", txn_id), rel="made")
        if merchant_name:
            self.g.add_edge(_n("user", user_id), _n("merchant", merchant_name), rel="transacts_with")
            self.g.add_edge(_n("transaction", txn_id), _n("merchant", merchant_name), rel="at")

    def add_investment(self, user_id: str, product_code: str):
        """添加投资持有关系"""
        self.g.add_edge(_n("user", user_id), _n("product", product_code), rel="holds")

    def add_transfer(self, from_user_id: str, to_user_id: str):
        """用户间转账关系"""
        self.g.add_edge(_n("user", from_user_id), _n("user", to_user_id), rel="transfers_to")

    # ------------------------------------------------ 图查询辅助

    def _successors_by_rel(self, node, rel: str) -> list:
        """关系命中的后继实体原始键（去掉 ("类型", key) 的类型前缀）。"""
        return [v[1] for _, v, r in self.g.out_edges(node, data="rel") if r == rel]

    def _user_txn_attrs(self, user_id: str, merchant_name=None) -> List[dict]:
        """取用户交易节点属性，可按商户过滤。"""
        out = []
        for _, tid, r in self.g.out_edges(_n("user", user_id), data="rel"):
            if r != "made":
                continue
            attrs = self.g.nodes[tid]
            if merchant_name is not None and attrs.get("merchant") != merchant_name:
                continue
            out.append(attrs)
        return out

    # ------------------------------------------------ 业务查询

    def get_user_merchants(self, user_id: str) -> set:
        """获取用户交易过的所有商户"""
        return set(self._successors_by_rel(_n("user", user_id), "transacts_with"))

    def get_user_products(self, user_id: str) -> set:
        """获取用户持有的所有产品"""
        return set(self._successors_by_rel(_n("user", user_id), "holds"))

    def get_merchant_users(self, merchant_name: str) -> set:
        """获取交易过某商户的所有用户"""
        return {
            u[1]
            for u, _, r in self.g.in_edges(_n("merchant", merchant_name), data="rel")
            if r == "transacts_with"
        }

    def detect_anomalies(self, user_id: str, merchant_name: str, amount: float) -> Dict:
        """
        异常检测：首次交易 / 金额远超该商户历史平均。

        Returns: {"is_anomaly", "reason", "risk_level"(low/medium/high)}
        """
        result = {"is_anomaly": False, "reason": None, "risk_level": "low"}

        # 检查 1：用户是否从未与该商户交易过
        if merchant_name not in self.get_user_merchants(user_id):
            result.update(is_anomaly=True, reason=f"用户首次与商户 {merchant_name} 交易", risk_level="medium")
            return result

        # 检查 2：交易金额是否异常（超过该商户历史平均金额的 3 倍）
        merchant_txns = self._user_txn_attrs(user_id, merchant_name)
        if merchant_txns:
            avg_amount = sum(abs(t.get("amount", 0)) for t in merchant_txns) / len(merchant_txns)
            if amount > avg_amount * 3:
                result.update(is_anomaly=True, reason=f"交易金额 {amount} 远超历史平均 {avg_amount:.2f}", risk_level="high")
                return result

        return result

    def recommend_products(self, user_id: str, risk_level: str) -> List[Dict]:
        """智能推荐：按风险等级推荐未持有产品，年化降序取前 5。"""
        held = self.get_user_products(user_id)
        recs = [
            attrs
            for n, attrs in self.g.nodes(data=True)
            if attrs.get("type") == "product"
            and attrs.get("risk_level") == risk_level
            and attrs.get("code", n[1]) not in held
        ]
        recs.sort(key=lambda x: x.get("annual_rate", 0), reverse=True)
        return recs[:5]

    def get_user_profile(self, user_id: str) -> Dict:
        """用户画像：账户/商户/产品/交易计数、Top 商户、风险等级。"""
        un = _n("user", user_id)
        user_info = self.g.nodes[un] if un in self.g else {}
        txns = self._user_txn_attrs(user_id)
        top_merchants = [m for m, _ in Counter(t["merchant"] for t in txns if t.get("merchant")).most_common(5)]

        return {
            "user_id": user_id,
            "account_count": len(self._successors_by_rel(un, "owns")),
            "merchant_count": len(self.get_user_merchants(user_id)),
            "product_count": len(self.get_user_products(user_id)),
            "transaction_count": len(txns),
            "top_merchants": top_merchants,
            "risk_level": user_info.get("risk_level", "unknown"),
        }

    def build_from_database(self):
        """从数据库构建知识图谱"""
        from app.data import repositories as repo

        users = repo.list_users()
        for user in users:
            self.add_user(user["id"], user)

        for user in users:
            for account in repo.list_accounts(user["id"]):
                self.add_account(account["id"], account, user["id"])

        txn_seq = 0
        for user in users:
            for txn in repo.transactions_since(user["id"], "2000-01-01"):
                merchant = txn.get("counterparty", "").replace("转账-", "")
                if merchant and _n("merchant", merchant) not in self.g:
                    self.add_merchant(merchant, {"name": merchant})
                txn_id = f"txn_{user['id']}_{txn_seq}"
                txn_seq += 1
                self.add_transaction(
                    txn_id, {**txn, "user_id": user["id"], "merchant": merchant}, user["id"], merchant
                )

        for product in repo.list_products():
            self.add_product(product["code"], product)

        for user in users:
            for inv in repo.list_investments(user["id"]):
                self.add_investment(user["id"], inv["product_code"])

    def to_dict(self) -> Dict:
        """导出图谱为 node/edge 列表（可直接喂前端可视化）。"""
        nodes = [
            {"id": f"{kind}:{key}", "type": kind, **{k: v for k, v in attrs.items() if k != "type"}}
            for (kind, key), attrs in self.g.nodes(data=True)
        ]
        edges = [
            {"source": f"{u[0]}:{u[1]}", "target": f"{v[0]}:{v[1]}", "rel": rel}
            for u, v, rel in self.g.edges(data="rel")
        ]
        return {"nodes": nodes, "edges": edges}


# 全局知识图谱实例
knowledge_graph = FinancialKnowledgeGraph()
