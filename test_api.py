import tempfile
import unittest
from pathlib import Path

from app import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.client = create_app({"TESTING": True, "DB_PATH": str(Path(self.tempdir.name) / "test.db"), "ADMIN_API_KEY": "test-secret", "CORS_ORIGINS": "*"}).test_client()
        self.admin = {"X-API-Key": "test-secret"}

    def tearDown(self):
        self.tempdir.cleanup()

    def identity(self, code="DOC"):
        result = {"esfm_ua": "ESFM Ejemplo", "especialidad": "Matemática", "ambito": "rural", "sexo": "F", "fecha": "2026-11-11", "codigo_aplicacion": code}
        if code.startswith("DOC"):
            result["anios_servicio"] = 12
        return result

    def test_public_questionnaire_and_template(self):
        self.assertEqual(self.client.get("/api/cuestionarios").status_code, 200)
        self.assertEqual(self.client.get("/api/cuestionarios/DIR").status_code, 200)
        self.assertEqual(self.client.get("/api/cuestionarios/EGR/plantilla").status_code, 200)
        self.assertEqual(self.client.get("/api/cuestionarios/nope").status_code, 404)

    def test_submission_duplicate_and_admin_list(self):
        payload = {"identificacion": self.identity(), "respuestas": {"1.1": 4, "1.2": {"valor": 5, "justificacion": "Motivo"}, "2.1": 3, "4.1": 4, "5.1": 2, "PA1": "Comentario"}}
        response = self.client.post("/api/respuestas/DOC", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.post("/api/respuestas/DOC", json=payload).status_code, 409)
        self.assertEqual(self.client.get("/api/respuestas").status_code, 401)
        listing = self.client.get("/api/respuestas?especialidad=Matemática", headers=self.admin)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.get_json()["total"], 1)

    def test_validation_partial_statistics_export_delete(self):
        incomplete = {"identificacion": self.identity("DOC-partial"), "respuestas": {"1.1": 4}}
        self.assertEqual(self.client.post("/api/respuestas/DOC", json=incomplete).status_code, 422)
        self.assertEqual(self.client.post("/api/respuestas/DOC?parcial=true", json=incomplete).status_code, 201)
        stats = self.client.get("/api/estadisticas/DOC", headers=self.admin)
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.get_json()["items"]["1.1"]["media"], 4)
        csv_response = self.client.get("/api/exportar/DOC.csv", headers=self.admin)
        self.assertEqual(csv_response.status_code, 200)
        self.assertTrue(csv_response.data.startswith(b"\xef\xbb\xbf"))
        response_id = self.client.get("/api/respuestas", headers=self.admin).get_json()["items"][0]["id"]
        self.assertEqual(self.client.delete(f"/api/respuestas/{response_id}", headers=self.admin).status_code, 200)

    def test_cors(self):
        response = self.client.get("/api/cuestionarios", headers={"Origin": "http://example.test"})
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")


if __name__ == "__main__":
    unittest.main()
