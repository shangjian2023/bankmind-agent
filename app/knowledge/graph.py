"""金融知识图谱：构建实体关系，支持智能推荐、异常检测、关联分析。"""

from typing import Dict, List, Optional, Set
from collections import defaultdict
import json


class FinancialKnowledgeGraph:
    """金融知识图谱"""

    def __init__(self):
        # 实体存储
        self.entities = {
            "user": {},      # user_id -> user_info
            "account": {},   # account_id -> account_info
            "merchant": {},  # merchant_name -> merchant_info
            "product": {},   # product_code -> product_info
            "transaction": {},  # txn_id -> txn_info
        }

        # 关系存储
        self.relationships = {
            "owns": defaultdict(set),        # user_id -> set(account_ids)
            "transacts_with": defaultdict(set),  # user_id -> set(merchant_names)
            "holds": defaultdict(set),       # user_id -> set(product_codes)
            "transfers_to": defaultdict(set),    # user_id -> set(target_user_ids)
        }

        # 统计信息
        self.statistics = {
            "user_merchant_count": defaultdict(int),  # user_id -> merchant_count
            "user_product_count": defaultdict(int),   # user_id -> product_count
            "merchant_transaction_count": defaultdict(int),  # merchant_name -> txn_count
        }

    def add_user(self, user_id: str, user_info: dict):
        """添加用户实体"""
        self.entities["user"][user_id] = user_info

    def add_account(self, account_id: str, account_info: dict, owner_id: str):
        """添加账户实体和拥有关系"""
        self.entities["account"][account_id] = account_info
        self.relationships["owns"][owner_id].add(account_id)

    def add_merchant(self, merchant_name: str, merchant_info: dict):
        """添加商户实体"""
        self.entities["merchant"][merchant_name] = merchant_info

    def add_product(self, product_code: str, product_info: dict):
        """添加产品实体"""
        self.entities["product"][product_code] = product_info

    def add_transaction(self, txn_id: str, txn_info: dict, user_id: str, merchant_name: Optional[str] = None):
        """添加交易实体和关系"""
        self.entities["transaction"][txn_id] = txn_info

        if merchant_name:
            self.relationships["transacts_with"][user_id].add(merchant_name)
            self.statistics["user_merchant_count"][user_id] = len(self.relationships["transacts_with"][user_id])
            self.statistics["merchant_transaction_count"][merchant_name] += 1

    def add_investment(self, user_id: str, product_code: str):
        """添加投资关系"""
        self.relationships["holds"][user_id].add(product_code)
        self.statistics["user_product_count"][user_id] = len(self.relationships["holds"][user_id])

    def get_user_merchants(self, user_id: str) -> Set[str]:
        """获取用户交易过的所有商户"""
        return self.relationships["transacts_with"].get(user_id, set())

    def get_user_products(self, user_id: str) -> Set[str]:
        """获取用户持有的所有产品"""
        return self.relationships["holds"].get(user_id, set())

    def get_merchant_users(self, merchant_name: str) -> Set[str]:
        """获取交易过某商户的所有用户"""
        return {uid for uid, merchants in self.relationships["transacts_with"].items()
                if merchant_name in merchants}

    def detect_anomalies(self, user_id: str, merchant_name: str, amount: float) -> Dict:
        """
        异常检测：检测用户与商户的交易是否异常

        Returns:
            {
                "is_anomaly": bool,
                "reason": str,
                "risk_level": str  # "low", "medium", "high"
            }
        """
        result = {"is_anomaly": False, "reason": None, "risk_level": "low"}

        # 检查 1：用户是否从未与该商户交易过
        if merchant_name not in self.get_user_merchants(user_id):
            result["is_anomaly"] = True
            result["reason"] = f"用户首次与商户 {merchant_name} 交易"
            result["risk_level"] = "medium"
            return result

        # 检查 2：交易金额是否异常（超过该商户历史平均金额的 3 倍）
        merchant_txns = [
            txn for txn in self.entities["transaction"].values()
            if txn.get("merchant") == merchant_name and txn.get("user_id") == user_id
        ]

        if merchant_txns:
            avg_amount = sum(abs(txn.get("amount", 0)) for txn in merchant_txns) / len(merchant_txns)
            if amount > avg_amount * 3:
                result["is_anomaly"] = True
                result["reason"] = f"交易金额 {amount} 远超历史平均 {avg_amount:.2f}"
                result["risk_level"] = "high"
                return result

        return result

    def recommend_products(self, user_id: str, risk_level: str) -> List[Dict]:
        """
        智能推荐：基于用户画像和风险偏好推荐产品

        Returns:
            List of recommended products
        """
        recommendations = []

        # 获取用户已持有的产品
        user_products = self.get_user_products(user_id)

        # 获取用户风险等级对应的产品
        risk_products = [
            p for p in self.entities["product"].values()
            if p.get("risk_level") == risk_level
        ]

        # 过滤已持有的产品
        for product in risk_products:
            if product["code"] not in user_products:
                recommendations.append(product)

        # 按年化收益率排序
        recommendations.sort(key=lambda x: x.get("annual_rate", 0), reverse=True)

        return recommendations[:5]  # 返回前 5 个推荐

    def get_user_profile(self, user_id: str) -> Dict:
        """
        获取用户画像

        Returns:
            {
                "user_id": str,
                "account_count": int,
                "merchant_count": int,
                "product_count": int,
                "transaction_count": int,
                "top_merchants": List[str],
                "risk_level": str
            }
        """
        user_info = self.entities["user"].get(user_id, {})

        # 统计交易数量
        user_txns = [
            txn for txn in self.entities["transaction"].values()
            if txn.get("user_id") == user_id
        ]

        # 获取 Top 商户
        merchant_counts = defaultdict(int)
        for txn in user_txns:
            if txn.get("merchant"):
                merchant_counts[txn["merchant"]] += 1

        top_merchants = sorted(merchant_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "user_id": user_id,
            "account_count": len(self.relationships["owns"].get(user_id, set())),
            "merchant_count": self.statistics["user_merchant_count"].get(user_id, 0),
            "product_count": self.statistics["user_product_count"].get(user_id, 0),
            "transaction_count": len(user_txns),
            "top_merchants": [m[0] for m in top_merchants],
            "risk_level": user_info.get("risk_level", "unknown"),
        }

    def build_from_database(self):
        """从数据库构建知识图谱"""
        from app.data import repositories as repo

        # 构建用户
        for user in repo.list_users():
            self.add_user(user["id"], user)

        # 构建账户
        for user_id in self.entities["user"]:
            accounts = repo.list_accounts(user_id)
            for account in accounts:
                self.add_account(account["id"], account, user_id)

        # 构建商户和交易
        for user_id in self.entities["user"]:
            transactions = repo.transactions_since(user_id, "2000-01-01")
            for txn in transactions:
                merchant = txn.get("counterparty", "").replace("转账-", "")
                if merchant and merchant not in self.entities["merchant"]:
                    self.add_merchant(merchant, {"name": merchant})

                txn_id = f"txn_{user_id}_{len(self.entities['transaction'])}"
                self.add_transaction(txn_id, {**txn, "user_id": user_id, "merchant": merchant}, user_id, merchant)

        # 构建产品和投资
        for product in repo.list_products():
            self.add_product(product["code"], product)

        for user_id in self.entities["user"]:
            investments = repo.list_investments(user_id)
            for inv in investments:
                self.add_investment(user_id, inv["product_code"])

    def to_dict(self) -> Dict:
        """导出图谱为字典"""
        return {
            "entities": self.entities,
            "relationships": {k: {uid: list(s) for uid, s in v.items()} for k, v in self.relationships.items()},
            "statistics": dict(self.statistics),
        }


# 全局知识图谱实例
knowledge_graph = FinancialKnowledgeGraph()
