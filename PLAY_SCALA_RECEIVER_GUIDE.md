# NGINX Amplify Agent - Play Scala Receiver Implementation Guide

This guide shows how to create a Play Framework application using Scala 3 that receives and stores metrics from the NGINX Amplify Agent.

## Overview

The NGINX Amplify Agent sends JSON payloads to two main endpoints:
- `POST /agent/` - Initial registration and configuration updates
- `POST /update/` - Regular metrics and data updates

## Project Setup

### build.sbt

```scala
ThisBuild / version := "1.0-SNAPSHOT"
ThisBuild / scalaVersion := "3.3.0"

lazy val root = (project in file("."))
  .enablePlugins(PlayScala)
  .settings(
    name := "nginx-monitoring",
    libraryDependencies ++= Seq(
      guice,
      "org.scalatestplus.play" %% "scalatestplus-play" % "5.1.0" % Test,
      "org.postgresql" % "postgresql" % "42.6.0",
      "org.playframework" %% "play-slick" % "6.0.0",
      "org.playframework" %% "play-slick-evolutions" % "6.0.0",
      "com.typesafe.play" %% "play-json" % "2.10.1",
      "org.mindrot" % "jbcrypt" % "0.4",
      "com.github.t3hnar" %% "scala-bcrypt" % "4.3.0"
    )
  )
```

## Database Schema (Evolutions)

### conf/evolutions/default/1.sql

```sql
# Organizations and API Keys

# --- !Ups

CREATE TABLE organizations (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    organization_id BIGINT REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP
);

CREATE TABLE monitored_objects (
    id BIGSERIAL PRIMARY KEY,
    uuid VARCHAR(255) UNIQUE NOT NULL,
    object_type VARCHAR(50) NOT NULL,
    hostname VARCHAR(255),
    imagename VARCHAR(255),
    local_id VARCHAR(255),
    root_uuid VARCHAR(255),
    organization_id BIGINT REFERENCES organizations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE metrics (
    id BIGSERIAL PRIMARY KEY,
    object_id BIGINT REFERENCES monitored_objects(id),
    metric_name VARCHAR(255) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_metadata (
    id BIGSERIAL PRIMARY KEY,
    object_id BIGINT REFERENCES monitored_objects(id),
    uname TEXT,
    platform VARCHAR(255),
    architecture VARCHAR(255),
    processor VARCHAR(255),
    python_version VARCHAR(50),
    agent_version VARCHAR(50),
    boot_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    object_id BIGINT REFERENCES monitored_objects(id),
    level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_object_timestamp ON metrics(object_id, timestamp);
CREATE INDEX idx_metrics_name_timestamp ON metrics(metric_name, timestamp);
CREATE INDEX idx_events_object_timestamp ON events(object_id, event_timestamp);
CREATE INDEX idx_objects_uuid ON monitored_objects(uuid);
CREATE INDEX idx_objects_org ON monitored_objects(organization_id);

# --- !Downs

DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS system_metadata;
DROP TABLE IF EXISTS metrics;
DROP TABLE IF EXISTS monitored_objects;
DROP TABLE IF EXISTS api_keys;
DROP TABLE IF EXISTS organizations;
```

## Models

### app/models/Organization.scala

```scala
package models

import play.api.libs.json.*
import slick.jdbc.PostgresProfile.api.*
import java.time.Instant

case class Organization(
  id: Option[Long] = None,
  name: String,
  slug: String,
  createdAt: Instant = Instant.now()
)

object Organization:
  given Format[Organization] = Json.format[Organization]

class OrganizationTable(tag: Tag) extends Table[Organization](tag, "organizations"):
  def id = column[Long]("id", O.PrimaryKey, O.AutoInc)
  def name = column[String]("name")
  def slug = column[String]("slug")
  def createdAt = column[Instant]("created_at")
  
  def * = (id.?, name, slug, createdAt).mapTo[Organization]
  def slugIndex = index("idx_org_slug", slug, unique = true)
```

### app/models/ApiKey.scala

```scala
package models

import play.api.libs.json.*
import slick.jdbc.PostgresProfile.api.*
import java.time.Instant
import java.security.MessageDigest
import scala.util.Random

case class ApiKey(
  id: Option[Long] = None,
  keyHash: String,
  organizationId: Long,
  name: String,
  isActive: Boolean = true,
  createdAt: Instant = Instant.now(),
  lastUsed: Option[Instant] = None
)

object ApiKey:
  given Format[ApiKey] = Json.format[ApiKey]
  
  def generateKey(): String = 
    Random.alphanumeric.take(43).mkString
  
  def hashKey(key: String): String =
    MessageDigest.getInstance("SHA-256")
      .digest(key.getBytes("UTF-8"))
      .map("%02x".format(_))
      .mkString

class ApiKeyTable(tag: Tag) extends Table[ApiKey](tag, "api_keys"):
  def id = column[Long]("id", O.PrimaryKey, O.AutoInc)
  def keyHash = column[String]("key_hash")
  def organizationId = column[Long]("organization_id")
  def name = column[String]("name")
  def isActive = column[Boolean]("is_active")
  def createdAt = column[Instant]("created_at")
  def lastUsed = column[Option[Instant]]("last_used")
  
  def * = (id.?, keyHash, organizationId, name, isActive, createdAt, lastUsed).mapTo[ApiKey]
  def organization = foreignKey("fk_apikey_org", organizationId, TableQuery[OrganizationTable])(_.id)
  def keyHashIndex = index("idx_apikey_hash", keyHash, unique = true)
```

### app/models/MonitoredObject.scala

```scala
package models

import play.api.libs.json.*
import slick.jdbc.PostgresProfile.api.*
import java.time.Instant

case class MonitoredObject(
  id: Option[Long] = None,
  uuid: String,
  objectType: String,
  hostname: Option[String] = None,
  imagename: Option[String] = None,
  localId: Option[String] = None,
  rootUuid: Option[String] = None,
  organizationId: Long,
  createdAt: Instant = Instant.now(),
  updatedAt: Instant = Instant.now(),
  isActive: Boolean = true
)

object MonitoredObject:
  given Format[MonitoredObject] = Json.format[MonitoredObject]

class MonitoredObjectTable(tag: Tag) extends Table[MonitoredObject](tag, "monitored_objects"):
  def id = column[Long]("id", O.PrimaryKey, O.AutoInc)
  def uuid = column[String]("uuid")
  def objectType = column[String]("object_type")
  def hostname = column[Option[String]]("hostname")
  def imagename = column[Option[String]]("imagename")
  def localId = column[Option[String]]("local_id")
  def rootUuid = column[Option[String]]("root_uuid")
  def organizationId = column[Long]("organization_id")
  def createdAt = column[Instant]("created_at")
  def updatedAt = column[Instant]("updated_at")
  def isActive = column[Boolean]("is_active")
  
  def * = (id.?, uuid, objectType, hostname, imagename, localId, rootUuid, organizationId, createdAt, updatedAt, isActive).mapTo[MonitoredObject]
  def organization = foreignKey("fk_object_org", organizationId, TableQuery[OrganizationTable])(_.id)
  def uuidIndex = index("idx_object_uuid", uuid, unique = true)
```

### app/models/Metric.scala

```scala
package models

import play.api.libs.json.*
import slick.jdbc.PostgresProfile.api.*
import java.time.Instant

case class Metric(
  id: Option[Long] = None,
  objectId: Long,
  metricName: String,
  metricValue: Double,
  timestamp: Instant,
  createdAt: Instant = Instant.now()
)

object Metric:
  given Format[Metric] = Json.format[Metric]

class MetricTable(tag: Tag) extends Table[Metric](tag, "metrics"):
  def id = column[Long]("id", O.PrimaryKey, O.AutoInc)
  def objectId = column[Long]("object_id")
  def metricName = column[String]("metric_name")
  def metricValue = column[Double]("metric_value")
  def timestamp = column[Instant]("timestamp")
  def createdAt = column[Instant]("created_at")
  
  def * = (id.?, objectId, metricName, metricValue, timestamp, createdAt).mapTo[Metric]
  def monitoredObject = foreignKey("fk_metric_object", objectId, TableQuery[MonitoredObjectTable])(_.id)
  def timestampIndex = index("idx_metric_timestamp", (objectId, timestamp))
```

## Services

### app/services/AuthService.scala

```scala
package services

import models.*
import slick.jdbc.PostgresProfile.api.*
import play.api.db.slick.DatabaseConfigProvider
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future}
import java.time.Instant

@Singleton
class AuthService @Inject()(
  dbConfigProvider: DatabaseConfigProvider
)(using ExecutionContext):
  
  private val db = dbConfigProvider.get.db
  private val organizations = TableQuery[OrganizationTable]
  private val apiKeys = TableQuery[ApiKeyTable]
  
  def authenticateApiKey(rawKey: String): Future[Option[(ApiKey, Organization)]] =
    val keyHash = ApiKey.hashKey(rawKey)
    val query = for
      apiKey <- apiKeys.filter(k => k.keyHash === keyHash && k.isActive)
      org <- organizations.filter(_.id === apiKey.organizationId)
    yield (apiKey, org)
    
    db.run(query.result.headOption).flatMap {
      case Some((key, org)) =>
        // Update last used timestamp
        val updateQuery = apiKeys.filter(_.id === key.id).map(_.lastUsed).update(Some(Instant.now()))
        db.run(updateQuery).map(_ => Some((key, org)))
      case None => Future.successful(None)
    }
  
  def createApiKey(organizationId: Long, name: String): Future[(String, ApiKey)] =
    val rawKey = ApiKey.generateKey()
    val keyHash = ApiKey.hashKey(rawKey)
    val apiKey = ApiKey(
      keyHash = keyHash,
      organizationId = organizationId,
      name = name
    )
    
    db.run((apiKeys returning apiKeys.map(_.id) into ((key, id) => key.copy(id = Some(id)))) += apiKey)
      .map(savedKey => (rawKey, savedKey))
```

### app/services/MonitoringService.scala

```scala
package services

import models.*
import slick.jdbc.PostgresProfile.api.*
import play.api.db.slick.DatabaseConfigProvider
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future}
import java.time.Instant

@Singleton
class MonitoringService @Inject()(
  dbConfigProvider: DatabaseConfigProvider
)(using ExecutionContext):
  
  private val db = dbConfigProvider.get.db
  private val objects = TableQuery[MonitoredObjectTable]
  private val metrics = TableQuery[MetricTable]
  
  def findOrCreateObject(
    uuid: String,
    objectType: String,
    hostname: Option[String],
    imagename: Option[String],
    organizationId: Long
  ): Future[MonitoredObject] =
    val query = objects.filter(o => o.uuid === uuid && o.organizationId === organizationId)
    
    db.run(query.result.headOption).flatMap {
      case Some(existing) =>
        // Update existing object
        val updated = existing.copy(
          hostname = hostname.orElse(existing.hostname),
          imagename = imagename.orElse(existing.imagename),
          updatedAt = Instant.now(),
          isActive = true
        )
        db.run(objects.filter(_.id === existing.id).update(updated)).map(_ => updated)
      
      case None =>
        // Create new object
        val newObject = MonitoredObject(
          uuid = uuid,
          objectType = objectType,
          hostname = hostname,
          imagename = imagename,
          organizationId = organizationId
        )
        db.run((objects returning objects.map(_.id) into ((obj, id) => obj.copy(id = Some(id)))) += newObject)
    }
  
  def storeMetrics(objectId: Long, metricsData: Map[String, List[(Double, Double)]]): Future[Int] =
    val metricRows = for
      (metricName, values) <- metricsData.toSeq
      (timestamp, value) <- values
    yield Metric(
      objectId = objectId,
      metricName = metricName,
      metricValue = value,
      timestamp = Instant.ofEpochSecond(timestamp.toLong)
    )
    
    db.run(metrics ++= metricRows).map(_.getOrElse(0))
```

## Controllers

### app/controllers/AgentController.scala

```scala
package controllers

import play.api.mvc.*
import play.api.libs.json.*
import services.{AuthService, MonitoringService}
import models.*
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future}
import java.time.Instant

@Singleton
class AgentController @Inject()(
  cc: ControllerComponents,
  authService: AuthService,
  monitoringService: MonitoringService
)(using ExecutionContext) extends AbstractController(cc):

  def register(apiKey: String): Action[JsValue] = Action.async(parse.json) { request =>
    authService.authenticateApiKey(apiKey).flatMap {
      case Some((_, organization)) =>
        val json = request.body
        val uuid = (json \ "uuid").asOpt[String]
        val objectType = (json \ "type").asOpt[String].getOrElse("system")
        val hostname = (json \ "hostname").asOpt[String]
        val imagename = (json \ "imagename").asOpt[String]
        
        uuid match
          case Some(id) =>
            monitoringService.findOrCreateObject(id, objectType, hostname, imagename, organization.id.get)
              .map { _ =>
                Ok(Json.obj(
                  "config" -> Json.obj(),
                  "messages" -> Json.arr(),
                  "versions" -> Json.obj(
                    "current" -> "1.7.0",
                    "obsolete" -> "1.0.0",
                    "old" -> "1.5.0"
                  ),
                  "capabilities" -> Json.obj(
                    "phpfpm" -> true,
                    "mysql" -> true
                  ),
                  "objects" -> Json.arr()
                ))
              }
          case None =>
            Future.successful(BadRequest(Json.obj("error" -> "UUID required")))
      
      case None =>
        Future.successful(Unauthorized(Json.obj("error" -> "Invalid API key")))
    }
  }

  def update(apiKey: String): Action[JsValue] = Action.async(parse.json) { request =>
    authService.authenticateApiKey(apiKey).flatMap {
      case Some((_, organization)) =>
        processPayload(request.body, organization.id.get).map { _ =>
          Ok(Json.obj("status" -> "success"))
        }.recover {
          case ex => InternalServerError(Json.obj("error" -> ex.getMessage))
        }
      
      case None =>
        Future.successful(Unauthorized(Json.obj("error" -> "Invalid API key")))
    }
  }

  private def processPayload(json: JsValue, organizationId: Long): Future[Unit] =
    json match
      case JsArray(payloads) =>
        Future.traverse(payloads)(payload => processSinglePayload(payload, organizationId)).map(_ => ())
      case payload =>
        processSinglePayload(payload, organizationId)

  private def processSinglePayload(json: JsValue, organizationId: Long): Future[Unit] =
    val objectData = (json \ "object").asOpt[JsObject].getOrElse(Json.obj())
    val uuid = (objectData \ "uuid").asOpt[String]
    
    uuid match
      case Some(id) =>
        for
          obj <- monitoringService.findOrCreateObject(
            id,
            (objectData \ "type").asOpt[String].getOrElse("system"),
            (objectData \ "hostname").asOpt[String],
            (objectData \ "imagename").asOpt[String],
            organizationId
          )
          _ <- storeMetrics(obj.id.get, (json \ "metrics").asOpt[JsObject].getOrElse(Json.obj()))
        yield ()
      
      case None =>
        Future.successful(())

  private def storeMetrics(objectId: Long, metricsJson: JsObject): Future[Unit] =
    val metricsData = metricsJson.fields.map { case (name, values) =>
      val valuesList = values.as[JsArray].value.map { arr =>
        val timestamp = arr.as[JsArray].value(0).as[Double]
        val value = arr.as[JsArray].value(1).as[Double]
        (timestamp, value)
      }.toList
      name -> valuesList
    }.toMap
    
    monitoringService.storeMetrics(objectId, metricsData).map(_ => ())
```

## Routes

### conf/routes

```
# Agent API endpoints
POST    /:apiKey/agent/                 controllers.AgentController.register(apiKey: String)
POST    /:apiKey/update/                controllers.AgentController.update(apiKey: String)

# Dashboard endpoints
GET     /                               controllers.DashboardController.index
GET     /dashboard                      controllers.DashboardController.dashboard
GET     /api/metrics/:uuid              controllers.DashboardController.metrics(uuid: String)

# Admin
GET     /admin                          controllers.AdminController.index
POST    /admin/organizations            controllers.AdminController.createOrganization
POST    /admin/api-keys                 controllers.AdminController.createApiKey
```

## Configuration

### conf/application.conf

```hocon
# Database configuration
slick.dbs.default.profile = "slick.jdbc.PostgresProfile$"
slick.dbs.default.db.driver = "org.postgresql.Driver"
slick.dbs.default.db.url = "jdbc:postgresql://localhost:5432/nginx_monitoring"
slick.dbs.default.db.user = "monitoring_user"
slick.dbs.default.db.password = "your_password"
slick.dbs.default.db.numThreads = 10
slick.dbs.default.db.maxConnections = 10

# Play configuration
play.http.parser.maxMemoryBuffer = 10MB
play.http.parser.maxDiskBuffer = 100MB

# Logging
logger.root = INFO
logger.play = INFO
logger.application = DEBUG
```

## Startup Script

### start_play_monitoring.sh

```bash
#!/bin/bash

set -e

PROJECT_DIR="/opt/nginx-monitoring-scala"
DB_NAME="nginx_monitoring"
DB_USER="monitoring_user"
DB_PASSWORD="secure_password"
PLAY_PORT="9000"

echo "Setting up Play Scala NGINX Monitoring System..."

# Install dependencies
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk postgresql postgresql-contrib sbt

# Setup PostgreSQL
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" || echo "Database exists"
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" || echo "User exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# Create project directory
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR
cd $PROJECT_DIR

# Initialize Play project if needed
if [ ! -f "build.sbt" ]; then
    sbt new playframework/play-scala-seed.g8 --name=nginx-monitoring
fi

# Run evolutions and start
sbt "runProd -Dhttp.port=$PLAY_PORT"
```

## Usage

1. **Setup:**
   ```bash
   chmod +x start_play_monitoring.sh
   ./start_play_monitoring.sh
   ```

2. **Create organization:**
   ```scala
   // In Play console
   val org = Organization(name = "Company A", slug = "company-a")
   val (rawKey, apiKey) = authService.createApiKey(org.id.get, "Default Key")
   ```

3. **Configure agent:**
   ```ini
   [cloud]
   api_url = http://localhost:9000/your-api-key/1.4
   ```

This Play Scala implementation provides the same functionality as the Django version with Scala 3 best practices, functional programming patterns, and type safety.