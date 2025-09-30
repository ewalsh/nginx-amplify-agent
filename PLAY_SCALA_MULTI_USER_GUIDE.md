# Play Scala Multi-User Authentication Guide

This guide extends the Play Scala receiver with comprehensive multi-user authentication and organization-based data isolation.

## Enhanced Models with User Management

### app/models/User.scala

```scala
package models

import play.api.libs.json.*
import slick.jdbc.PostgresProfile.api.*
import com.github.t3hnar.bcrypt.*
import java.time.Instant

case class User(
  id: Option[Long] = None,
  email: String,
  passwordHash: String,
  firstName: Option[String] = None,
  lastName: Option[String] = None,
  isActive: Boolean = true,
  createdAt: Instant = Instant.now(),
  lastLogin: Option[Instant] = None
):
  def checkPassword(password: String): Boolean = 
    password.isBcryptedSafeBounded(passwordHash).getOrElse(false)

object User:
  given Format[User] = Json.format[User]
  
  def hashPassword(password: String): String = password.bcryptSafeBounded.get

class UserTable(tag: Tag) extends Table[User](tag, "users"):
  def id = column[Long]("id", O.PrimaryKey, O.AutoInc)
  def email = column[String]("email")
  def passwordHash = column[String]("password_hash")
  def firstName = column[Option[String]]("first_name")
  def lastName = column[Option[String]]("last_name")
  def isActive = column[Boolean]("is_active")
  def createdAt = column[Instant]("created_at")
  def lastLogin = column[Option[Instant]]("last_login")
  
  def * = (id.?, email, passwordHash, firstName, lastName, isActive, createdAt, lastLogin).mapTo[User]
  def emailIndex = index("idx_user_email", email, unique = true)
```

### app/models/OrganizationMembership.scala

```scala
package models

import play.api.libs.json.*
import slick.jdbc.PostgresProfile.api.*
import java.time.Instant

enum Role:
  case Admin, Member, Viewer
  
  def canWrite: Boolean = this match
    case Admin | Member => true
    case Viewer => false
  
  def canAdmin: Boolean = this == Admin

object Role:
  given Format[Role] = Json.formatEnum(Role)

case class OrganizationMembership(
  id: Option[Long] = None,
  userId: Long,
  organizationId: Long,
  role: Role = Role.Member,
  createdAt: Instant = Instant.now()
)

object OrganizationMembership:
  given Format[OrganizationMembership] = Json.format[OrganizationMembership]

class OrganizationMembershipTable(tag: Tag) extends Table[OrganizationMembership](tag, "organization_memberships"):
  def id = column[Long]("id", O.PrimaryKey, O.AutoInc)
  def userId = column[Long]("user_id")
  def organizationId = column[Long]("organization_id")
  def role = column[Role]("role")
  def createdAt = column[Instant]("created_at")
  
  def * = (id.?, userId, organizationId, role, createdAt).mapTo[OrganizationMembership]
  def user = foreignKey("fk_membership_user", userId, TableQuery[UserTable])(_.id)
  def organization = foreignKey("fk_membership_org", organizationId, TableQuery[OrganizationTable])(_.id)
  def uniqueMembership = index("idx_unique_membership", (userId, organizationId), unique = true)
  
  given MappedColumnType[Role, String] = MappedColumnType.base[Role, String](
    _.toString,
    Role.valueOf
  )
```

### app/models/Session.scala

```scala
package models

import play.api.libs.json.*
import slick.jdbc.PostgresProfile.api.*
import java.time.Instant
import java.util.UUID

case class Session(
  id: Option[Long] = None,
  sessionId: String = UUID.randomUUID().toString,
  userId: Long,
  organizationId: Option[Long] = None,
  createdAt: Instant = Instant.now(),
  expiresAt: Instant = Instant.now().plusSeconds(86400), // 24 hours
  isActive: Boolean = true
)

object Session:
  given Format[Session] = Json.format[Session]

class SessionTable(tag: Tag) extends Table[Session](tag, "sessions"):
  def id = column[Long]("id", O.PrimaryKey, O.AutoInc)
  def sessionId = column[String]("session_id")
  def userId = column[Long]("user_id")
  def organizationId = column[Option[Long]]("organization_id")
  def createdAt = column[Instant]("created_at")
  def expiresAt = column[Instant]("expires_at")
  def isActive = column[Boolean]("is_active")
  
  def * = (id.?, sessionId, userId, organizationId, createdAt, expiresAt, isActive).mapTo[Session]
  def user = foreignKey("fk_session_user", userId, TableQuery[UserTable])(_.id)
  def sessionIndex = index("idx_session_id", sessionId, unique = true)
```

## Enhanced Services

### app/services/UserService.scala

```scala
package services

import models.*
import slick.jdbc.PostgresProfile.api.*
import play.api.db.slick.DatabaseConfigProvider
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future}
import java.time.Instant

@Singleton
class UserService @Inject()(
  dbConfigProvider: DatabaseConfigProvider
)(using ExecutionContext):
  
  private val db = dbConfigProvider.get.db
  private val users = TableQuery[UserTable]
  private val memberships = TableQuery[OrganizationMembershipTable]
  private val sessions = TableQuery[SessionTable]
  
  def authenticate(email: String, password: String): Future[Option[User]] =
    db.run(users.filter(u => u.email === email && u.isActive).result.headOption).map {
      case Some(user) if user.checkPassword(password) =>
        // Update last login
        db.run(users.filter(_.id === user.id).map(_.lastLogin).update(Some(Instant.now())))
        Some(user)
      case _ => None
    }
  
  def createUser(email: String, password: String, firstName: Option[String] = None, lastName: Option[String] = None): Future[User] =
    val user = User(
      email = email,
      passwordHash = User.hashPassword(password),
      firstName = firstName,
      lastName = lastName
    )
    db.run((users returning users.map(_.id) into ((user, id) => user.copy(id = Some(id)))) += user)
  
  def getUserOrganizations(userId: Long): Future[Seq[(Organization, Role)]] =
    val query = for
      membership <- memberships.filter(_.userId === userId)
      org <- TableQuery[OrganizationTable].filter(_.id === membership.organizationId)
    yield (org, membership.role)
    
    db.run(query.result)
  
  def createSession(userId: Long, organizationId: Option[Long] = None): Future[Session] =
    val session = Session(userId = userId, organizationId = organizationId)
    db.run((sessions returning sessions.map(_.id) into ((session, id) => session.copy(id = Some(id)))) += session)
  
  def validateSession(sessionId: String): Future[Option[(User, Session, Option[Organization])]] =
    val query = for
      session <- sessions.filter(s => s.sessionId === sessionId && s.isActive && s.expiresAt > Instant.now())
      user <- users.filter(_.id === session.userId)
      org <- TableQuery[OrganizationTable].filter(_.id === session.organizationId).result.headOption
    yield (user, session, org)
    
    db.run(query.result.headOption).map(_.map { case (user, session, org) => (user, session, org) })
```

### app/services/OrganizationService.scala

```scala
package services

import models.*
import slick.jdbc.PostgresProfile.api.*
import play.api.db.slick.DatabaseConfigProvider
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future}

@Singleton
class OrganizationService @Inject()(
  dbConfigProvider: DatabaseConfigProvider,
  authService: AuthService
)(using ExecutionContext):
  
  private val db = dbConfigProvider.get.db
  private val organizations = TableQuery[OrganizationTable]
  private val memberships = TableQuery[OrganizationMembershipTable]
  
  def createOrganization(name: String, slug: String, adminUserId: Long): Future[(Organization, String)] =
    db.run {
      (for
        org <- (organizations returning organizations.map(_.id) into ((org, id) => org.copy(id = Some(id)))) += Organization(name = name, slug = slug)
        _ <- memberships += OrganizationMembership(userId = adminUserId, organizationId = org.id.get, role = Role.Admin)
      yield org).transactionally
    }.flatMap { org =>
      authService.createApiKey(org.id.get, "Default Key").map { case (rawKey, _) =>
        (org, rawKey)
      }
    }
  
  def addMember(organizationId: Long, userId: Long, role: Role = Role.Member): Future[OrganizationMembership] =
    val membership = OrganizationMembership(userId = userId, organizationId = organizationId, role = role)
    db.run((memberships returning memberships.map(_.id) into ((membership, id) => membership.copy(id = Some(id)))) += membership)
  
  def getUserRole(userId: Long, organizationId: Long): Future[Option[Role]] =
    db.run(memberships.filter(m => m.userId === userId && m.organizationId === organizationId).map(_.role).result.headOption)
  
  def getOrganizationMembers(organizationId: Long): Future[Seq[(User, Role)]] =
    val query = for
      membership <- memberships.filter(_.organizationId === organizationId)
      user <- TableQuery[UserTable].filter(_.id === membership.userId)
    yield (user, membership.role)
    
    db.run(query.result)
```

## Authentication Actions

### app/actions/AuthenticatedAction.scala

```scala
package actions

import play.api.mvc.*
import play.api.mvc.Results.*
import services.UserService
import models.{User, Session, Organization}
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future}

case class AuthenticatedRequest[A](
  user: User,
  session: Session,
  organization: Option[Organization],
  request: Request[A]
) extends WrappedRequest[A](request)

@Singleton
class AuthenticatedAction @Inject()(
  parser: BodyParsers.Default,
  userService: UserService
)(using ExecutionContext) extends ActionBuilder[AuthenticatedRequest, AnyContent]:
  
  override def executionContext: ExecutionContext = implicitly[ExecutionContext]
  override def parser: BodyParser[AnyContent] = parser
  
  override def invokeBlock[A](request: Request[A], block: AuthenticatedRequest[A] => Future[Result]): Future[Result] =
    request.session.get("sessionId") match
      case Some(sessionId) =>
        userService.validateSession(sessionId).flatMap {
          case Some((user, session, org)) =>
            block(AuthenticatedRequest(user, session, org, request))
          case None =>
            Future.successful(Unauthorized("Invalid session").withNewSession)
        }
      case None =>
        Future.successful(Unauthorized("Authentication required"))

case class ApiAuthenticatedRequest[A](
  organization: Organization,
  apiKey: models.ApiKey,
  request: Request[A]
) extends WrappedRequest[A](request)

@Singleton
class ApiAuthenticatedAction @Inject()(
  parser: BodyParsers.Default,
  authService: AuthService
)(using ExecutionContext):
  
  def apply(apiKeyParam: String): ActionBuilder[ApiAuthenticatedRequest, AnyContent] = 
    new ActionBuilder[ApiAuthenticatedRequest, AnyContent]:
      override def executionContext: ExecutionContext = implicitly[ExecutionContext]
      override def parser: BodyParser[AnyContent] = parser
      
      override def invokeBlock[A](request: Request[A], block: ApiAuthenticatedRequest[A] => Future[Result]): Future[Result] =
        authService.authenticateApiKey(apiKeyParam).flatMap {
          case Some((apiKey, organization)) =>
            block(ApiAuthenticatedRequest(organization, apiKey, request))
          case None =>
            Future.successful(Unauthorized("Invalid API key"))
        }
```

## Enhanced Controllers

### app/controllers/AuthController.scala

```scala
package controllers

import play.api.mvc.*
import play.api.libs.json.*
import play.api.data.*
import play.api.data.Forms.*
import services.{UserService, OrganizationService}
import actions.AuthenticatedAction
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future}

case class LoginForm(email: String, password: String)
case class RegisterForm(email: String, password: String, firstName: Option[String], lastName: Option[String], organizationName: String)

@Singleton
class AuthController @Inject()(
  cc: ControllerComponents,
  userService: UserService,
  organizationService: OrganizationService,
  authenticatedAction: AuthenticatedAction
)(using ExecutionContext) extends AbstractController(cc):

  private val loginForm = Form(
    mapping(
      "email" -> email,
      "password" -> nonEmptyText(minLength = 6)
    )(LoginForm.apply)(LoginForm.unapply)
  )
  
  private val registerForm = Form(
    mapping(
      "email" -> email,
      "password" -> nonEmptyText(minLength = 6),
      "firstName" -> optional(text),
      "lastName" -> optional(text),
      "organizationName" -> nonEmptyText
    )(RegisterForm.apply)(RegisterForm.unapply)
  )

  def login: Action[AnyContent] = Action.async { implicit request =>
    loginForm.bindFromRequest().fold(
      formWithErrors => Future.successful(BadRequest(views.html.login(formWithErrors))),
      loginData => {
        userService.authenticate(loginData.email, loginData.password).flatMap {
          case Some(user) =>
            userService.createSession(user.id.get).map { session =>
              Redirect(routes.DashboardController.index)
                .withSession("sessionId" -> session.sessionId)
            }
          case None =>
            Future.successful(BadRequest(views.html.login(loginForm.withGlobalError("Invalid credentials"))))
        }
      }
    )
  }

  def register: Action[AnyContent] = Action.async { implicit request =>
    registerForm.bindFromRequest().fold(
      formWithErrors => Future.successful(BadRequest(views.html.register(formWithErrors))),
      registerData => {
        for
          user <- userService.createUser(registerData.email, registerData.password, registerData.firstName, registerData.lastName)
          (org, apiKey) <- organizationService.createOrganization(registerData.organizationName, registerData.organizationName.toLowerCase.replaceAll("\\s+", "-"), user.id.get)
          session <- userService.createSession(user.id.get, Some(org.id.get))
        yield Redirect(routes.DashboardController.index)
          .withSession("sessionId" -> session.sessionId)
          .flashing("success" -> s"Account created! Your API key: $apiKey")
      }
    )
  }

  def logout: Action[AnyContent] = authenticatedAction { request =>
    Redirect(routes.AuthController.loginForm).withNewSession
  }
```

### app/controllers/DashboardController.scala

```scala
package controllers

import play.api.mvc.*
import play.api.libs.json.*
import services.{MonitoringService, OrganizationService}
import actions.AuthenticatedAction
import models.Role
import javax.inject.{Inject, Singleton}
import scala.concurrent.{ExecutionContext, Future}

@Singleton
class DashboardController @Inject()(
  cc: ControllerComponents,
  authenticatedAction: AuthenticatedAction,
  monitoringService: MonitoringService,
  organizationService: OrganizationService
)(using ExecutionContext) extends AbstractController(cc):

  def index: Action[AnyContent] = authenticatedAction.async { request =>
    for
      organizations <- userService.getUserOrganizations(request.user.id.get)
      objects <- monitoringService.getObjectsForOrganizations(organizations.map(_._1.id.get))
    yield Ok(views.html.dashboard(request.user, organizations, objects))
  }

  def organizationDashboard(orgId: Long): Action[AnyContent] = authenticatedAction.async { request =>
    organizationService.getUserRole(request.user.id.get, orgId).flatMap {
      case Some(role) =>
        monitoringService.getObjectsForOrganization(orgId).map { objects =>
          Ok(views.html.organizationDashboard(request.user, orgId, role, objects))
        }
      case None =>
        Future.successful(Forbidden("Access denied"))
    }
  }

  def metrics(objectUuid: String): Action[AnyContent] = authenticatedAction.async { request =>
    for
      userOrgs <- userService.getUserOrganizations(request.user.id.get)
      orgIds = userOrgs.map(_._1.id.get)
      objectOpt <- monitoringService.getObjectByUuid(objectUuid, orgIds)
      result <- objectOpt match
        case Some(obj) =>
          monitoringService.getRecentMetrics(obj.id.get).map { metrics =>
            Ok(Json.obj(
              "object" -> Json.obj(
                "uuid" -> obj.uuid,
                "hostname" -> obj.hostname,
                "type" -> obj.objectType
              ),
              "metrics" -> metrics.map { m =>
                Json.obj(
                  "name" -> m.metricName,
                  "value" -> m.metricValue,
                  "timestamp" -> m.timestamp.toString
                )
              }
            ))
          }
        case None =>
          Future.successful(NotFound("Object not found"))
    yield result
  }
```

## Database Evolutions

### conf/evolutions/default/2.sql

```sql
# User Management Tables

# --- !Ups

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE organization_memberships (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    organization_id BIGINT REFERENCES organizations(id),
    role VARCHAR(50) DEFAULT 'Member',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, organization_id)
);

CREATE TABLE sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id BIGINT REFERENCES users(id),
    organization_id BIGINT REFERENCES organizations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_session_id ON sessions(session_id);
CREATE INDEX idx_membership_user_org ON organization_memberships(user_id, organization_id);

# --- !Downs

DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS organization_memberships;
DROP TABLE IF EXISTS users;
```

## Routes with Authentication

### conf/routes

```
# Authentication
GET     /login                          controllers.AuthController.loginForm
POST    /login                          controllers.AuthController.login
GET     /register                       controllers.AuthController.registerForm
POST    /register                       controllers.AuthController.register
POST    /logout                         controllers.AuthController.logout

# Dashboard (authenticated users)
GET     /                               controllers.DashboardController.index
GET     /dashboard                      controllers.DashboardController.index
GET     /org/:orgId                     controllers.DashboardController.organizationDashboard(orgId: Long)
GET     /api/metrics/:uuid              controllers.DashboardController.metrics(uuid: String)

# Agent API (API key authenticated)
POST    /:apiKey/agent/                 controllers.AgentController.register(apiKey: String)
POST    /:apiKey/update/                controllers.AgentController.update(apiKey: String)

# Admin
GET     /admin                          controllers.AdminController.index
POST    /admin/organizations            controllers.AdminController.createOrganization
POST    /admin/users                    controllers.AdminController.createUser
```

This Play Scala implementation provides:

- **Type-safe authentication** with custom actions
- **Role-based access control** using Scala enums
- **Session management** with automatic expiration
- **Organization isolation** ensuring data security
- **Functional programming** patterns throughout
- **Compile-time safety** for all database operations

The system ensures complete data isolation between organizations while providing a clean, type-safe API for both agent communication and user dashboard access.