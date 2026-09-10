{
  "rules": {
    ".read": false,
    ".write": false,

    "users": {
      ".read": "auth !== null",
      "$uid": {
        ".write": "auth !== null && auth.uid === $uid"
      }
    },

    "requests": {
      ".read": "auth !== null",
      "$requestId": {
        ".write": "auth !== null && ((!data.exists() && newData.child('senderUid').val() === auth.uid) || (data.exists() && (data.child('senderUid').val() === auth.uid || data.child('receiverUid').val() === auth.uid)))"
      }
    },

    "chats": {
      "$conversationId": {
        ".read": "auth !== null",
        ".write": "auth !== null",
        "messages": {
          "$messageId": {
            ".validate": "newData.child('senderUid').isString() && newData.child('text').isString() && newData.child('text').val().length <= 4000"
          }
        }
      }
    },

    "voiceCalls": {
      ".indexOn": ["calleeId", "callerId"],
      "$callId": {
        ".read": "auth !== null && (data.child('callerId').val() === auth.uid || data.child('calleeId').val() === auth.uid)",
        ".write": "auth !== null && ((!data.exists() && newData.child('callerId').val() === auth.uid) || (data.exists() && (data.child('callerId').val() === auth.uid || data.child('calleeId').val() === auth.uid)))",
        ".validate": "newData.child('callerId').isString() && newData.child('calleeId').isString() && newData.child('status').isString()"
      }
    },

    "notifications": {
      "$uid": {
        ".read": "auth !== null && auth.uid === $uid",
        ".write": "auth !== null"
      }
    },

    "sessions": {
      ".read": "auth !== null",
      "$sessionId": {
        ".write": "auth !== null && ((!data.exists() && newData.child('host_uid').val() === auth.uid) || (data.exists() && (data.child('host_uid').val() === auth.uid || data.child('guest_uid').val() === auth.uid)))"
      }
    },

    "reviews": {
      ".read": "auth !== null",
      "$reviewId": {
        ".write": "auth !== null && (!data.exists() && newData.child('authorUid').val() === auth.uid)"
      }
    },

    "posts": {
      ".read": "auth !== null",
      "$postId": {
        ".write": "auth !== null && ((!data.exists() && newData.child('authorUid').val() === auth.uid) || (data.exists() && data.child('authorUid').val() === auth.uid))"
      }
    },

    "postLikes": {
      ".read": "auth !== null",
      "$postId": {
        "$uid": {
          ".write": "auth !== null && auth.uid === $uid"
        }
      }
    },

    "groups": {
      ".read": "auth !== null",
      "$groupId": {
        ".write": "auth !== null"
      }
    },

    "groupMembers": {
      "$groupId": {
        ".read": "auth !== null",
        "$uid": {
          ".write": "auth !== null && auth.uid === $uid"
        }
      }
    },

    "groupIdeas": {
      "$groupId": {
        ".read": "auth !== null",
        ".write": "auth !== null"
      }
    },

    "favorites": {
      "$uid": {
        ".read": "auth !== null && auth.uid === $uid",
        ".write": "auth !== null && auth.uid === $uid"
      }
    },

    "learningPlans": {
      "$uid": {
        ".read": "auth !== null && auth.uid === $uid",
        ".write": "auth !== null && auth.uid === $uid"
      }
    },

    "gamification": {
      "$uid": {
        ".read": "auth !== null && auth.uid === $uid",
        ".write": "auth !== null && auth.uid === $uid"
      }
    },

    "presence": {
      "$uid": {
        ".read": "auth !== null",
        ".write": "auth !== null && auth.uid === $uid"
      }
    },

    "profileViews": {
      ".read": "auth !== null",
      "$viewId": {
        ".write": "auth !== null"
      }
    },

    "listings": {
      ".read": "auth !== null",
      "$listingId": {
        ".write": "auth !== null"
      }
    },

    "blocks": {
      "$uid": {
        ".read": "auth !== null && auth.uid === $uid",
        ".write": "auth !== null && auth.uid === $uid"
      }
    },

    "reports": {
      "$reportId": {
        ".write": "auth !== null && (!data.exists() && newData.child('reporterUid').val() === auth.uid)"
      }
    }
  }
}
