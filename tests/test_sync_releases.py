import unittest

from tools.sync_releases import latest_allowed_nvidia, version_numbers


class ReleaseSelectionTests(unittest.TestCase):
    def test_numeric_revision_order(self):
        self.assertGreater(version_numbers("595.99.02-10"), version_numbers("595.99.02-9"))

    def test_only_latest_allowed_package_versions_survive(self):
        allowlist = {
            "syno-nvidia-driver-kver5-595-proprietary": {"repo": "syno_nvidia_driver"},
            "syno-nvidia-gpu-monitor": {"repo": "syno-gpu-monitor"},
        }
        records = [
            {"repo": "syno_nvidia_driver", "info": {"package": "syno-nvidia-driver-kver5-595-proprietary", "version": "595.99.02-3"}},
            {"repo": "syno_nvidia_driver", "info": {"package": "syno-nvidia-driver-kver5-595-proprietary", "version": "595.99.02-4"}},
            {"repo": "syno_nvidia_driver", "info": {"package": "syno-nvidia-driver-kver5-595-open", "version": "595.99.02-99"}},
            {"repo": "syno-gpu-monitor", "info": {"package": "syno-nvidia-gpu-monitor", "version": "0.6.7"}},
            {"repo": "syno-gpu-monitor", "info": {"package": "syno-nvidia-gpu-monitor", "version": "0.6.8"}},
            {"repo": "syno-amdgpu-driver", "info": {"package": "syno-amdgpu-driver", "version": "0.5.2"}},
        ]

        selected, removed = latest_allowed_nvidia(records, allowlist)

        self.assertEqual(removed, 3)
        self.assertEqual({(item["repo"], item["info"]["version"]) for item in selected}, {
            ("syno_nvidia_driver", "595.99.02-4"),
            ("syno-gpu-monitor", "0.6.8"),
            ("syno-amdgpu-driver", "0.5.2"),
        })


if __name__ == "__main__":
    unittest.main()
