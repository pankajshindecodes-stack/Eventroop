from rest_framework.routers import DefaultRouter
from .views import *

app_name = 'booking'
router = DefaultRouter()
router.register("public-venues", PublicVenueViewSet, basename="public-venues")
router.register("public-services", PublicServiceViewSet, basename="public-services")
router.register("patients", PatientViewSet, basename="patients")
router.register("location", LocationViewSet, basename="location")
router.register("packages", PackageViewSet, basename="package")

urlpatterns = router.urls

{
  "info": {
    "name": "Booking Packages API",
    "description": "Package API for booking system",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000"
    },
    {
      "key": "token",
      "value": "YOUR_ACCESS_TOKEN"
    },
    {
      "key": "package_id",
      "value": ""
    }
  ],
  "item": [
    {
      "name": "List Packages",
      "request": {
        "method": "GET",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "url": {
          "raw": "{{base_url}}/booking/packages/",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", ""]
        }
      }
    },
    {
      "name": "Create Package",
      "request": {
        "method": "POST",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"name\": \"Premium OPD Package\",\n  \"description\": \"Includes doctor visit + lab tests\",\n  \"package_type\": \"OPD\",\n  \"price\": 1500,\n  \"is_active\": true,\n  \"content_type\": 12,\n  \"object_id\": 3\n}"
        },
        "url": {
          "raw": "{{base_url}}/booking/packages/",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", ""]
        }
      }
    },
    {
      "name": "Get Package By ID",
      "request": {
        "method": "GET",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "url": {
          "raw": "{{base_url}}/booking/packages/{{package_id}}/",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", "{{package_id}}", ""]
        }
      }
    },
    {
      "name": "Update Package",
      "request": {
        "method": "PATCH",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"price\": 1800,\n  \"is_active\": true\n}"
        },
        "url": {
          "raw": "{{base_url}}/booking/packages/{{package_id}}/",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", "{{package_id}}", ""]
        }
      }
    },
    {
      "name": "Delete Package",
      "request": {
        "method": "DELETE",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "url": {
          "raw": "{{base_url}}/booking/packages/{{package_id}}/",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", "{{package_id}}", ""]
        }
      }
    },
    {
      "name": "Filter By Package Type",
      "request": {
        "method": "GET",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "url": {
          "raw": "{{base_url}}/booking/packages/by_type/?type=OPD",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", "by_type", ""],
          "query": [
            { "key": "type", "value": "OPD" }
          ]
        }
      }
    },
    {
      "name": "Filter By Belongs To",
      "request": {
        "method": "GET",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "url": {
          "raw": "{{base_url}}/booking/packages/by_belongs_to/?content_type=venue&object_id=3",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", "by_belongs_to", ""],
          "query": [
            { "key": "content_type", "value": "venue" },
            { "key": "object_id", "value": "3" }
          ]
        }
      }
    },
    {
      "name": "Search Packages",
      "request": {
        "method": "GET",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "url": {
          "raw": "{{base_url}}/booking/packages/?search=premium",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", ""],
          "query": [
            { "key": "search", "value": "premium" }
          ]
        }
      }
    },
    {
      "name": "Order Packages By Price",
      "request": {
        "method": "GET",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "url": {
          "raw": "{{base_url}}/booking/packages/?ordering=price",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", ""],
          "query": [
            { "key": "ordering", "value": "price" }
          ]
        }
      }
    },
    {
      "name": "Filter By is_active",
      "request": {
        "method": "GET",
        "authentication": [
          { "key": "Bearer", "value": "{{access_token}}" }
        ],
        "url": {
          "raw": "{{base_url}}/booking/packages/?is_active=true",
          "host": ["{{base_url}}"],
          "path": ["booking", "packages", ""],
          "query": [
            { "key": "is_active", "value": "true" }
          ]
        }
      }
    }
  ]
}
