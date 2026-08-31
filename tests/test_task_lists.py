"""タスクリスト管理 (PC手帳リスト管理UI・roadmap 1.6 / 階層化 1.6-R) のユニットテスト。

TickTick風リスト分類のDB層の挙動を検証する:
- リスト作成・一覧取得・名称変更 (rename_task_list)
- リスト削除時の所属タスクの未分類 (list_id=NULL) 移行
- update_task によるタスクのリスト間移動 (list_id 変更)
- parent_id による階層ツリー (作成・移動・循環防止・削除時の子昇格)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402


class TestTaskLists(unittest.TestCase):
    """タスクリストCRUDの振る舞いテスト (テンポラリDBを使用)。"""

    def setUp(self):
        """テストごとに独立したテンポラリDBを用意する。"""
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_task_lists.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        database.init_db(self.db_path)

    def tearDown(self):
        """テンポラリDBを後片付けする。"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_and_get_task_list(self):
        """リスト作成 → 一覧取得で絵文字・名前が反映される"""
        list_id = database.create_task_list("仕事", emoji="💼", db_path=self.db_path)
        lists = database.get_task_lists(db_path=self.db_path)
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].id, list_id)
        self.assertEqual(lists[0].name, "仕事")
        self.assertEqual(lists[0].emoji, "💼")

    def test_create_empty_name_raises(self):
        """空名のリスト作成はValueErrorになる"""
        with self.assertRaises(ValueError):
            database.create_task_list("   ", db_path=self.db_path)

    def test_rename_task_list(self):
        """rename_task_list で名称変更でき、絵文字は変更しない限り保持される"""
        list_id = database.create_task_list("仕事", emoji="💼", db_path=self.db_path)
        self.assertTrue(database.rename_task_list(list_id, "顧客対応", db_path=self.db_path))
        lst = database.get_task_lists(db_path=self.db_path)[0]
        self.assertEqual(lst.name, "顧客対応")
        self.assertEqual(lst.emoji, "💼")
        # 絵文字も同時に変更できる
        self.assertTrue(database.rename_task_list(list_id, "自宅", emoji="🏠", db_path=self.db_path))
        lst = database.get_task_lists(db_path=self.db_path)[0]
        self.assertEqual(lst.name, "自宅")
        self.assertEqual(lst.emoji, "🏠")

    def test_rename_empty_name_raises(self):
        """空名への変更はValueErrorになる"""
        list_id = database.create_task_list("仕事", db_path=self.db_path)
        with self.assertRaises(ValueError):
            database.rename_task_list(list_id, "", db_path=self.db_path)

    def test_rename_missing_list_returns_false(self):
        """存在しないリストへの変更はFalseを返す"""
        self.assertFalse(database.rename_task_list(99999, "どこか", db_path=self.db_path))

    def test_task_assignment_and_filtering(self):
        """タスクにリストを割り当て、update_task でリスト間移動できる"""
        work = database.create_task_list("仕事", db_path=self.db_path)
        home = database.create_task_list("家", db_path=self.db_path)
        task_id = database.create_task(database.Task(title="資料作成", list_id=work), db_path=self.db_path)
        # 作成時の割り当て確認
        tasks = database.get_tasks(status="todo", db_path=self.db_path)
        self.assertEqual(tasks[0].list_id, work)
        # update_task (ホワイトリスト list_id) でリスト間移動
        self.assertTrue(database.update_task(task_id, {"list_id": home}, db_path=self.db_path))
        tasks = database.get_tasks(status="todo", db_path=self.db_path)
        self.assertEqual(tasks[0].list_id, home)

    def test_delete_list_moves_tasks_to_unsorted(self):
        """リスト削除時、所属タスクは list_id=NULL (未分類) へ移行される"""
        work = database.create_task_list("仕事", db_path=self.db_path)
        task_id = database.create_task(database.Task(title="請求書処理", list_id=work), db_path=self.db_path)
        self.assertTrue(database.delete_task_list(work, db_path=self.db_path))
        self.assertEqual(database.get_task_lists(db_path=self.db_path), [])
        tasks = database.get_tasks(status="todo", db_path=self.db_path)
        self.assertEqual(len(tasks), 1)
        self.assertIsNone(tasks[0].list_id)

    # =========================================================================
    # 🌳 リスト階層化 (Block 1.6-R)
    # =========================================================================
    def test_create_list_with_parent(self):
        """parent_id 指定で作成したリストは親情報を保持する"""
        parent_id = database.create_task_list("プライベート", emoji="🏠", db_path=self.db_path)
        child_id = database.create_task_list("買い物", emoji="🛒", parent_id=parent_id, db_path=self.db_path)
        lists = {l.id: l for l in database.get_task_lists(db_path=self.db_path)}
        self.assertEqual(lists[child_id].parent_id, parent_id)
        self.assertIsNone(lists[parent_id].parent_id)

    def test_create_list_with_missing_parent_raises(self):
        """存在しない親リストIDを指定した作成はValueErrorになる"""
        with self.assertRaises(ValueError):
            database.create_task_list("孤儿", parent_id=99999, db_path=self.db_path)

    def test_move_task_list(self):
        """move_task_list でリストを別の親の下へ移動でき、最上位へも戻せる"""
        parent_a = database.create_task_list("A", db_path=self.db_path)
        parent_b = database.create_task_list("B", db_path=self.db_path)
        child = database.create_task_list("子", parent_id=parent_a, db_path=self.db_path)
        # A → B へ移動
        self.assertTrue(database.move_task_list(child, parent_b, db_path=self.db_path))
        lists = {l.id: l for l in database.get_task_lists(db_path=self.db_path)}
        self.assertEqual(lists[child].parent_id, parent_b)
        # B → 最上位へ移動
        self.assertTrue(database.move_task_list(child, None, db_path=self.db_path))
        lists = {l.id: l for l in database.get_task_lists(db_path=self.db_path)}
        self.assertIsNone(lists[child].parent_id)

    def test_move_task_list_missing_source_returns_false(self):
        """存在しないリストの移動はFalseを返す"""
        self.assertFalse(database.move_task_list(99999, None, db_path=self.db_path))

    def test_move_task_list_cycle_raises(self):
        """自分自身または子孫を親に指定した移動はValueError (循環参照防止)"""
        parent = database.create_task_list("親", db_path=self.db_path)
        child = database.create_task_list("子", parent_id=parent, db_path=self.db_path)
        grandchild = database.create_task_list("孫", parent_id=child, db_path=self.db_path)
        # 自分自身を親に指定
        with self.assertRaises(ValueError):
            database.move_task_list(parent, parent, db_path=self.db_path)
        # 直接の子を親に指定
        with self.assertRaises(ValueError):
            database.move_task_list(parent, child, db_path=self.db_path)
        # 孫を親に指定 (間接循環)
        with self.assertRaises(ValueError):
            database.move_task_list(parent, grandchild, db_path=self.db_path)
        # 存在しない移動先もValueError
        with self.assertRaises(ValueError):
            database.move_task_list(child, 99999, db_path=self.db_path)

    def test_delete_list_promotes_children(self):
        """リスト削除時、子リストは削除対象の親へ昇格する (ツリー分断の防止)"""
        grand = database.create_task_list("祖父", db_path=self.db_path)
        parent = database.create_task_list("親", parent_id=grand, db_path=self.db_path)
        child = database.create_task_list("子", parent_id=parent, db_path=self.db_path)
        # 親を削除 → 子は祖父へ昇格
        self.assertTrue(database.delete_task_list(parent, db_path=self.db_path))
        lists = {l.id: l for l in database.get_task_lists(db_path=self.db_path)}
        self.assertIn(child, lists)
        self.assertEqual(lists[child].parent_id, grand)
        # ルート削除時は子がルートへ昇格する
        self.assertTrue(database.delete_task_list(grand, db_path=self.db_path))
        lists = {l.id: l for l in database.get_task_lists(db_path=self.db_path)}
        self.assertIsNone(lists[child].parent_id)


if __name__ == "__main__":
    unittest.main()
